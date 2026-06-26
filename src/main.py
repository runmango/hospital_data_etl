"""Command line entrypoint for the hospital data ETL."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import AppConfig, canonical_source_name, load_config
from .exporters.csv_exporter import export_dataframe_to_csv
from .exporters.excel_exporter import export_dataframes_to_excel
from .extractors.his import extract_patient_diagnosis_bundle
from .extractors.lis import discover_lis_tables, inspect_lis_table
from .extractors.ris import extract_ris_dimage
from .extractors.metadata import (
    DEFAULT_EXCLUDED_OWNERS,
    extract_table_columns,
    inspect_his_tables,
    list_accessible_tables,
    search_columns_by_keywords,
)
from .oracle_client import OracleClient, OracleClientError
from .utils.logger import setup_logger
from .validators import validate_date_range


DATASOURCE_CHOICES = ["his", "his1", "his1r", "lis", "ris"]
HIS_SOURCE_CHOICES = ["his", "his1", "his1r"]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _safe_name(value: str) -> str:
    return value.upper().replace("$", "_").replace("#", "_")


def _build_client(config: AppConfig, source: str, logger) -> OracleClient:
    datasource = config.get_datasource_config(source)
    return OracleClient(datasource, logger=logger, source_name=datasource.name)


def _validate_positive_limit(limit: int, maximum: int | None = None) -> int:
    if limit < 1:
        raise ValueError("limit must be greater than 0")
    if maximum is not None and limit > maximum:
        raise ValueError(f"limit must not exceed {maximum}")
    return limit


def _date_span_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    return (end - start).days + 1


def _print_dataframe(dataframe: pd.DataFrame, max_rows: int = 50) -> None:
    if dataframe.empty:
        print("No rows returned.")
        return
    with pd.option_context("display.max_rows", max_rows, "display.max_columns", None, "display.width", 180):
        print(dataframe.to_string(index=False))


def command_test_connection(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    logger.info("Testing datasource connection: %s", args.source)

    with _build_client(config, args.source, logger) as client:
        client.test_connection()

    summary = {
        "source": datasource.name,
        "host": datasource.host,
        "port": datasource.port,
        "service_name": datasource.service_name,
        "username": datasource.username,
        "connected": True,
        "tested_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path = _write_json(summary, config.output_dir / f"connection_{datasource.name}_{_timestamp()}.json")
    logger.info(
        "Datasource connection test succeeded: source=%s host=%s service_name=%s summary=%s",
        datasource.name,
        datasource.host,
        datasource.service_name,
        summary_path,
    )
    return 0


def command_list_tables(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    limit = _validate_positive_limit(args.limit, maximum=1000)
    logger.info("Listing accessible Oracle tables: source=%s, limit=%s", datasource.name, limit)

    with _build_client(config, args.source, logger) as client:
        dataframe = list_accessible_tables(client, limit=limit)

    _print_dataframe(dataframe, max_rows=limit)
    output_path = export_dataframe_to_csv(dataframe, config.output_dir / f"{datasource.name}_tables.csv")
    logger.info("Accessible table list exported: %s rows -> %s", len(dataframe), output_path)
    return 0


def command_inspect_schema(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    logger.info(
        "Inspecting Oracle table schema: source=%s, owner=%s, table=%s",
        datasource.name,
        args.owner,
        args.table,
    )

    with _build_client(config, args.source, logger) as client:
        dataframe = extract_table_columns(client, owner=args.owner, table_name=args.table)

    _print_dataframe(dataframe)
    output_name = f"{datasource.name}_{_safe_name(args.owner)}_{_safe_name(args.table)}_schema.csv"
    output_path = export_dataframe_to_csv(dataframe, config.output_dir / output_name)
    logger.info("Table schema exported: %s rows -> %s", len(dataframe), output_path)
    return 0


def command_search_columns(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    limit = _validate_positive_limit(args.limit, maximum=1000)
    keywords = config.lis_discovery.column_keywords if datasource.name == "lis" else (
        "PATIENT", "BRXH", "ZYH", "MZH", "EXAM", "REPORT", "IMAGE", "DICOM", "STUDY", "ACCESSION", "JC", "BG"
    )
    logger.info("Searching Oracle candidate columns: source=%s, limit=%s", datasource.name, limit)

    with _build_client(config, args.source, logger) as client:
        dataframe = search_columns_by_keywords(
            client,
            keywords=keywords,
            excluded_owners=DEFAULT_EXCLUDED_OWNERS,
            limit=limit,
        )

    _print_dataframe(dataframe, max_rows=limit)
    output_path = export_dataframe_to_csv(
        dataframe,
        config.output_dir / f"{datasource.name}_columns_candidates.csv",
    )
    logger.info("Candidate column list exported: %s rows -> %s", len(dataframe), output_path)
    return 0


def command_inspect_his(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    logger.info("Inspecting HIS table columns: source=%s", datasource.name)

    with _build_client(config, args.source, logger) as client:
        metadata = inspect_his_tables(client)

    timestamp = _timestamp()
    brjbxx_csv = export_dataframe_to_csv(
        metadata["brjbxx_columns"],
        config.output_dir / f"{datasource.name}_brjbxx_columns_{timestamp}.csv",
    )
    brzdqk_csv = export_dataframe_to_csv(
        metadata["brzdqk_columns"],
        config.output_dir / f"{datasource.name}_brzdqk_columns_{timestamp}.csv",
    )
    workbook = export_dataframes_to_excel(
        {
            "brjbxx_columns": metadata["brjbxx_columns"],
            "brzdqk_columns": metadata["brzdqk_columns"],
        },
        config.output_dir / f"{datasource.name}_his_columns_{timestamp}.xlsx",
    )

    logger.info("BRJBXX columns exported: %s rows -> %s", len(metadata["brjbxx_columns"]), brjbxx_csv)
    logger.info("BRZDQK columns exported: %s rows -> %s", len(metadata["brzdqk_columns"]), brzdqk_csv)
    logger.info("HIS columns workbook exported: %s", workbook)
    return 0


def command_extract_his(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    if datasource.name not in {"his1", "his1r"}:
        raise ValueError("extract-his supports only his/his1/his1r sources")
    if datasource.name == "his1r":
        warning = (
            "Warning: HIS1r is intended for query/ops validation. "
            "Make sure this source is approved for programmatic extraction."
        )
        print(warning)
        logger.warning(warning)

    start_date, end_date = validate_date_range(args.start_date, args.end_date)
    span_days = _date_span_days(start_date, end_date)
    max_days = config.extract.default_max_days_without_force
    if span_days > max_days and not args.force:
        raise ValueError(
            f"HIS extract date range is {span_days} days, exceeding {max_days}. "
            "Use --force only after approval."
        )

    logger.info(
        "Extracting HIS patient and diagnosis range: source=%s, %s to %s",
        datasource.name,
        start_date,
        end_date,
    )

    with _build_client(config, args.source, logger) as client:
        bundle = extract_patient_diagnosis_bundle(client, start_date, end_date)

    patients_path = export_dataframe_to_csv(
        bundle["patients"],
        config.output_dir / f"patients_{start_date}_{end_date}.csv",
    )
    diagnosis_path = export_dataframe_to_csv(
        bundle["diagnosis"],
        config.output_dir / f"diagnosis_{start_date}_{end_date}.csv",
    )
    workbook_path = export_dataframes_to_excel(
        {
            "patients": bundle["patients"],
            "diagnosis": bundle["diagnosis"],
            "summary": bundle["summary"],
        },
        config.output_dir / f"his_patient_diagnosis_{start_date}_{end_date}.xlsx",
    )
    summary = dict(bundle["summary"])
    summary["source"] = datasource.name
    summary_path = _write_json(
        summary,
        config.output_dir / f"summary_{start_date}_{end_date}.json",
    )

    logger.info(
        "HIS extraction completed: source=%s, patients=%s, diagnosis=%s, unique_brxh=%s, linked=%s",
        datasource.name,
        summary["patient_count"],
        summary["diagnosis_count"],
        summary["unique_brxh_count"],
        summary["has_patient_diagnosis_link"],
    )
    logger.info("Patients CSV exported: %s", patients_path)
    logger.info("Diagnosis CSV exported: %s", diagnosis_path)
    logger.info("Patient diagnosis workbook exported: %s", workbook_path)
    logger.info("Summary JSON exported: %s", summary_path)
    return 0


def command_discover_lis(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    logger.info("Discovering LIS metadata")

    with _build_client(config, "lis", logger) as client:
        bundle = discover_lis_tables(client, config.lis_discovery)

    timestamp = _timestamp()
    owners_csv = export_dataframe_to_csv(bundle["owners"], config.output_dir / f"lis_owners_{timestamp}.csv")
    tables_csv = export_dataframe_to_csv(
        bundle["accessible_tables"],
        config.output_dir / f"lis_accessible_tables_{timestamp}.csv",
    )
    candidate_tables_csv = export_dataframe_to_csv(
        bundle["candidate_tables"],
        config.output_dir / f"lis_candidate_tables_{timestamp}.csv",
    )
    candidate_columns_csv = export_dataframe_to_csv(
        bundle["candidate_columns"],
        config.output_dir / f"lis_candidate_columns_{timestamp}.csv",
    )
    workbook = export_dataframes_to_excel(
        {
            "owners": bundle["owners"],
            "accessible_tables": bundle["accessible_tables"],
            "candidate_tables": bundle["candidate_tables"],
            "candidate_columns": bundle["candidate_columns"],
            "summary": bundle["summary"],
        },
        config.output_dir / f"lis_discovery_{timestamp}.xlsx",
    )
    logger.info("LIS owners exported: %s", owners_csv)
    logger.info("LIS accessible tables exported: %s", tables_csv)
    logger.info("LIS candidate tables exported: %s", candidate_tables_csv)
    logger.info("LIS candidate columns exported: %s", candidate_columns_csv)
    logger.info("LIS discovery workbook exported: %s", workbook)
    return 0


def command_inspect_lis_table(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    sample_limit = _validate_positive_limit(args.sample_limit, maximum=100)
    logger.info(
        "Inspecting LIS table: owner=%s, table=%s, sample_limit=%s",
        args.owner,
        args.table,
        sample_limit,
    )

    with _build_client(config, "lis", logger) as client:
        bundle = inspect_lis_table(client, args.owner, args.table, sample_limit=sample_limit)

    timestamp = _timestamp()
    owner = _safe_name(args.owner)
    table = _safe_name(args.table)
    columns_csv = export_dataframe_to_csv(
        bundle["columns"],
        config.output_dir / f"lis_{owner}_{table}_columns_{timestamp}.csv",
    )
    sample_csv = export_dataframe_to_csv(
        bundle["sample"],
        config.output_dir / f"lis_{owner}_{table}_sample_{timestamp}.csv",
    )
    workbook = export_dataframes_to_excel(
        {
            "columns": bundle["columns"],
            "sample": bundle["sample"],
            "summary": bundle["summary"],
        },
        config.output_dir / f"lis_{owner}_{table}_inspect_{timestamp}.xlsx",
    )
    logger.info("LIS table columns exported: %s rows -> %s", len(bundle["columns"]), columns_csv)
    logger.info("LIS table sample exported: %s rows -> %s", len(bundle["sample"]), sample_csv)
    logger.info("LIS table inspect workbook exported: %s", workbook)
    return 0



def command_export_ris_dimage(args) -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)
    datasource = config.get_datasource_config(args.source)
    if datasource.name != "ris":
        raise ValueError("export-ris-dimage currently supports only the ris datasource")
    limit = _validate_positive_limit(args.limit, maximum=100000)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = config.output_dir / output_path if len(output_path.parts) == 1 else Path(output_path)

    logger.info("Exporting RIS_DIMAGE: source=%s, limit=%s", datasource.name, limit)
    with _build_client(config, args.source, logger) as client:
        dataframe = extract_ris_dimage(client, limit=limit)

    exported_path = export_dataframe_to_csv(dataframe, output_path)
    logger.info("RIS_DIMAGE CSV exported: rows=%s -> %s", len(dataframe), exported_path)
    print("Preview (first 10 rows):")
    _print_dataframe(dataframe.head(10), max_rows=10)
    print(f"RIS_DIMAGE CSV exported: rows={len(dataframe)} -> {exported_path}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Hospital Oracle ETL minimum closed-loop tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    test_parser = subparsers.add_parser("test-connection", help="Test datasource connection.")
    test_parser.add_argument("--source", default="his", choices=DATASOURCE_CHOICES, help="Datasource name.")
    test_parser.set_defaults(func=command_test_connection)

    list_parser = subparsers.add_parser("list-tables", help="List accessible Oracle tables.")
    list_parser.add_argument("--source", default="ris", choices=DATASOURCE_CHOICES, help="Datasource name.")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum rows to return, max 1000.")
    list_parser.set_defaults(func=command_list_tables)

    schema_parser = subparsers.add_parser("inspect-schema", help="Inspect an Oracle table schema.")
    schema_parser.add_argument("--source", default="ris", choices=DATASOURCE_CHOICES, help="Datasource name.")
    schema_parser.add_argument("--owner", required=True, help="Oracle table owner.")
    schema_parser.add_argument("--table", required=True, help="Oracle table name.")
    schema_parser.set_defaults(func=command_inspect_schema)

    search_parser = subparsers.add_parser("search-columns", help="Search candidate business columns.")
    search_parser.add_argument("--source", default="ris", choices=DATASOURCE_CHOICES, help="Datasource name.")
    search_parser.add_argument("--limit", type=int, default=200, help="Maximum rows to return, max 1000.")
    search_parser.set_defaults(func=command_search_columns)

    inspect_parser = subparsers.add_parser("inspect-his", help="Export HIS table column metadata.")
    inspect_parser.add_argument("--source", default="his1", choices=HIS_SOURCE_CHOICES, help="HIS datasource name.")
    inspect_parser.set_defaults(func=command_inspect_his)

    extract_parser = subparsers.add_parser("extract-his", help="Extract HIS patients and diagnosis.")
    extract_parser.add_argument("--source", default="his1", choices=HIS_SOURCE_CHOICES, help="HIS datasource name.")
    extract_parser.add_argument("--start-date", required=True, help="Start discharge date, YYYYMMDD.")
    extract_parser.add_argument("--end-date", required=True, help="End discharge date, YYYYMMDD.")
    extract_parser.add_argument("--force", action="store_true", help="Allow date ranges longer than configured safety limit.")
    extract_parser.set_defaults(func=command_extract_his)

    discover_lis_parser = subparsers.add_parser("discover-lis", help="Discover LIS owners, tables and candidate columns.")
    discover_lis_parser.set_defaults(func=command_discover_lis)

    inspect_lis_parser = subparsers.add_parser("inspect-lis-table", help="Inspect a LIS table and export a small sample.")
    inspect_lis_parser.add_argument("--owner", required=True, help="LIS table owner.")
    inspect_lis_parser.add_argument("--table", required=True, help="LIS table name.")
    inspect_lis_parser.add_argument("--sample-limit", type=int, default=10, help="Sample row limit, max 100.")
    inspect_lis_parser.set_defaults(func=command_inspect_lis_table)

    export_ris_parser = subparsers.add_parser("export-ris-dimage", help="Export JK_WSB.RIS_DIMAGE image path rows to CSV.")
    export_ris_parser.add_argument("--source", default="ris", choices=["ris"], help="RIS datasource name.")
    export_ris_parser.add_argument("--limit", type=int, default=1000, help="Maximum rows to export.")
    export_ris_parser.add_argument("--output", default="outputs/ris_dimage.csv", help="Output CSV path.")
    export_ris_parser.set_defaults(func=command_export_ris_dimage)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except (OracleClientError, ValueError, FileNotFoundError) as exc:
        config = load_config()
        logger = setup_logger(config.log_dir)
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())





