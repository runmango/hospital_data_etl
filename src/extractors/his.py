"""HIS patient and diagnosis extractors."""

from __future__ import annotations

import pandas as pd

from ..oracle_client import OracleClient


def extract_patients(client: OracleClient, start_date: str, end_date: str) -> pd.DataFrame:
    return client.query_sql_file(
        "sql/his/extract_patients.sql",
        params={"start_date": start_date, "end_date": end_date},
    )


def extract_diagnosis_by_patient_range(
    client: OracleClient,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    return client.query_sql_file(
        "sql/his/extract_diagnosis.sql",
        params={"start_date": start_date, "end_date": end_date},
    )


def _unique_brxh_count(patients_df: pd.DataFrame) -> int:
    for column in patients_df.columns:
        if column.lower() == "brxh":
            return int(patients_df[column].dropna().nunique())
    return 0


def _has_patient_diagnosis_link(
    patients_df: pd.DataFrame,
    diagnosis_df: pd.DataFrame,
) -> bool:
    patient_key = next((column for column in patients_df.columns if column.lower() == "brxh"), None)
    diagnosis_key = next((column for column in diagnosis_df.columns if column.lower() == "brxh"), None)
    if patient_key is None or diagnosis_key is None:
        return False
    if patients_df.empty or diagnosis_df.empty:
        return False

    patient_ids = set(patients_df[patient_key].dropna().astype(str))
    diagnosis_ids = set(diagnosis_df[diagnosis_key].dropna().astype(str))
    return bool(patient_ids.intersection(diagnosis_ids))


def extract_patient_diagnosis_bundle(
    client: OracleClient,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    patients_df = extract_patients(client, start_date, end_date)
    diagnosis_df = extract_diagnosis_by_patient_range(client, start_date, end_date)

    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "patient_count": int(len(patients_df)),
        "diagnosis_count": int(len(diagnosis_df)),
        "unique_brxh_count": _unique_brxh_count(patients_df),
        "has_patient_diagnosis_link": _has_patient_diagnosis_link(patients_df, diagnosis_df),
    }

    return {
        "patients": patients_df,
        "diagnosis": diagnosis_df,
        "summary": summary,
    }

