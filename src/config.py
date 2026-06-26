"""Application configuration loading."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DataSourceConfig:
    name: str
    type: str
    host: str
    port: int
    service_name: str
    username: str
    password: str
    mode: str = "thin"
    client_lib_dir: str = ""
    username_env: str = ""
    password_env: str = ""


@dataclass(frozen=True)
class ExtractConfig:
    default_start_date: str
    default_end_date: str
    batch_size: int
    default_max_days_without_force: int


@dataclass(frozen=True)
class TableConfig:
    patient_table: str
    diagnosis_table: str
    patient_key: str
    discharge_date_field: str


@dataclass(frozen=True)
class LisDiscoveryConfig:
    excluded_owners: tuple[str, ...]
    table_keywords: tuple[str, ...]
    column_keywords: tuple[str, ...]


@dataclass(frozen=True)
class AppConfig:
    datasources: dict[str, DataSourceConfig]
    extract: ExtractConfig
    tables: TableConfig
    lis_discovery: LisDiscoveryConfig
    output_dir: Path
    log_dir: Path

    def get_datasource_config(self, source: str) -> DataSourceConfig:
        canonical = canonical_source_name(source)
        try:
            return self.datasources[canonical]
        except KeyError as exc:
            known_sources = ", ".join(["his", *sorted(self.datasources)])
            raise ValueError(f"Unknown datasource '{source}'. Known sources: {known_sources}") from exc

    def get_datasource(self, source: str) -> DataSourceConfig:
        return self.get_datasource_config(source)

def canonical_source_name(source: str) -> str:
    value = source.lower().strip()
    if value == "his":
        return "his1"
    return value


def _interpolate_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _interpolate_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    if not isinstance(value, str):
        return value

    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    return pattern.sub(lambda match: os.getenv(match.group(1), ""), value)


def _load_yaml_config() -> dict[str, Any]:
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must contain a YAML mapping at the top level.")
    return _interpolate_env(data)


def _resolve_dir(path_value: str | None, default_name: str) -> Path:
    raw_path = path_value or default_name
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _first_env(names: list[str]) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def _env_names(source: str, key: str) -> list[str]:
    if source == "his1":
        return [f"HIS1_{key}", f"HIS_{key}"]
    if source == "ris":
        return [f"RIS_DB_{key}", f"RIS_{key}"]
    return [f"{source.upper()}_{key}"]


def _datasource_defaults(source: str) -> dict[str, str]:
    defaults = {
        "his1": {
            "host": "192.168.0.65",
            "port": "1521",
            "service_name": "orcl",
            "username": "jk_wsb",
            "password": "",
            "mode": "thin",
        },
        "his1r": {
            "host": "192.168.220.10",
            "port": "15065",
            "service_name": "orcl",
            "username": "jk_wsb",
            "password": "",
            "mode": "thin",
        },
        "lis": {
            "host": "192.168.211.85",
            "port": "1521",
            "service_name": "lisdb",
            "username": "",
            "password": "",
            "mode": "thin",
        },
        "ris": {
            "host": "192.168.211.87",
            "port": "1521",
            "service_name": "ris",
            "username": "",
            "password": "",
            "mode": "thick",
        },
    }
    return defaults.get(
        source,
        {
            "host": "",
            "port": "1521",
            "service_name": "",
            "username": "",
            "password": "",
            "mode": "thin",
        },
    )


def _datasource_from_values(source: str, values: dict[str, Any]) -> DataSourceConfig:
    defaults = _datasource_defaults(source)
    username_envs = _env_names(source, "USERNAME")
    password_envs = _env_names(source, "PASSWORD")

    host = str(values.get("host") or _first_env(_env_names(source, "HOST")) or defaults["host"])
    port = int(values.get("port") or _first_env(_env_names(source, "PORT")) or defaults["port"])
    service_name = str(
        values.get("service_name")
        or _first_env(_env_names(source, "SERVICE_NAME"))
        or defaults["service_name"]
    )
    username = str(values.get("username") or _first_env(username_envs) or defaults["username"])
    password = str(values.get("password") or _first_env(password_envs) or defaults["password"])

    thick_mode = values.get("thick_mode")
    mode = str(values.get("mode") or os.getenv("ORACLE_CLIENT_MODE", "") or defaults["mode"]).lower()
    if isinstance(thick_mode, bool):
        mode = "thick" if thick_mode else "thin"

    client_lib_dir = str(values.get("client_lib_dir") or os.getenv("ORACLE_CLIENT_LIB_DIR", ""))
    if client_lib_dir:
        client_path = Path(client_lib_dir)
        if not client_path.is_absolute():
            client_lib_dir = str(BASE_DIR / client_path)
    if mode not in {"thin", "thick"}:
        raise ValueError("ORACLE_CLIENT_MODE must be either 'thin' or 'thick'.")

    return DataSourceConfig(
        name=source,
        type=str(values.get("type") or "oracle"),
        host=host,
        port=port,
        service_name=service_name,
        username=username,
        password=password,
        mode=mode,
        client_lib_dir=client_lib_dir,
        username_env=username_envs[0],
        password_env=password_envs[0],
    )


def _parse_table_config(raw_tables: dict[str, Any]) -> TableConfig:
    his_tables = raw_tables.get("his", {}) if isinstance(raw_tables.get("his"), dict) else raw_tables
    return TableConfig(
        patient_table=str(his_tables.get("patient_table", "jk_wsb.brjbxx")),
        diagnosis_table=str(his_tables.get("diagnosis_table", "jk_wsb.brzdqk")),
        patient_key=str(his_tables.get("patient_key", "brxh")),
        discharge_date_field=str(his_tables.get("discharge_date_field", "cyrq")),
    )


def _parse_lis_discovery(yaml_config: dict[str, Any]) -> LisDiscoveryConfig:
    values = yaml_config.get("lis_discovery", {})
    return LisDiscoveryConfig(
        excluded_owners=tuple(
            values.get(
                "excluded_owners",
                ["SYS", "SYSTEM", "XDB", "MDSYS", "CTXSYS", "ORDSYS", "DBSNMP"],
            )
        ),
        table_keywords=tuple(
            values.get(
                "table_keywords",
                [
                    "LIS",
                    "RESULT",
                    "REPORT",
                    "TEST",
                    "SAMPLE",
                    "ITEM",
                    "INSPECTION",
                    "CHECK",
                    "LAB",
                    "JY",
                    "JYBG",
                    "JYMX",
                    "JYJG",
                ],
            )
        ),
        column_keywords=tuple(
            values.get(
                "column_keywords",
                [
                    "PATIENT",
                    "PAT",
                    "BR",
                    "BRID",
                    "BRXH",
                    "ZYH",
                    "MZH",
                    "XM",
                    "NAME",
                    "SEX",
                    "AGE",
                    "ITEM",
                    "TEST",
                    "RESULT",
                    "VALUE",
                    "UNIT",
                    "RANGE",
                    "FLAG",
                    "REPORT",
                    "SAMPLE",
                    "TIME",
                    "DATE",
                ],
            )
        ),
    )



def load_config() -> AppConfig:
    """Load .env and optional config.yaml into typed config objects."""
    load_dotenv(BASE_DIR / ".env")
    yaml_config = _load_yaml_config()

    configured_datasources = yaml_config.get("datasources", {})
    datasource_names = {canonical_source_name(name) for name in configured_datasources}
    datasource_names |= {"his1", "his1r", "lis", "ris"}
    datasources = {
        name: _datasource_from_values(name, configured_datasources.get(name, {}))
        for name in sorted(datasource_names)
    }

    extract_values = yaml_config.get("extract", {})
    extract = ExtractConfig(
        default_start_date=str(extract_values.get("default_start_date", "20240301")),
        default_end_date=str(extract_values.get("default_end_date", "20240303")),
        batch_size=int(extract_values.get("batch_size", 1000)),
        default_max_days_without_force=int(extract_values.get("default_max_days_without_force", 31)),
    )

    tables = _parse_table_config(yaml_config.get("tables", {}))
    lis_discovery = _parse_lis_discovery(yaml_config)

    path_values = yaml_config.get("paths", {})
    output_dir = _resolve_dir(path_values.get("output_dir") or os.getenv("OUTPUT_DIR"), "outputs")
    log_dir = _resolve_dir(path_values.get("log_dir") or os.getenv("LOG_DIR"), "logs")

    return AppConfig(
        datasources=datasources,
        extract=extract,
        tables=tables,
        lis_discovery=lis_discovery,
        output_dir=output_dir,
        log_dir=log_dir,
    )




