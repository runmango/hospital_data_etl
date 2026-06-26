"""Small Oracle client wrapper for pandas based ETL jobs."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

import pandas as pd

from .config import BASE_DIR, DataSourceConfig
from .utils.secret_redactor import redact_text, short_sha256


class OracleClientError(RuntimeError):
    """Raised when Oracle connection or query execution fails."""


_THICK_MODE_INITIALIZED = False


_ORACLE_ERROR_HINTS = {
    "DPI-1047": "Oracle Instant Client failed to load. Check ORACLE_CLIENT_LIB_DIR and PATH/LD_LIBRARY_PATH.",
    "DPY-3010": "python-oracledb thin mode does not support this older Oracle server; use thick mode.",
    "ORA-01017": "Oracle username or password is invalid.",
    "ORA-01031": "Oracle user has insufficient privileges.",
    "ORA-00604": "Oracle login trigger or recursive SQL failed on the database side.",
    "ORA-00942": "Oracle table or view does not exist, or the user has no permission.",
    "ORA-12170": "Oracle TCP connection timed out; check network, firewall, and listener reachability.",
    "ORA-12514": "Oracle listener does not know the requested service_name.",
    "ORA-12541": "Oracle listener is not reachable or not running.",
}


def _mask_username(username: str) -> str:
    if not username:
        return "<empty>"
    if len(username) <= 2:
        return username[0] + "*"
    return username[0] + "*" * (len(username) - 2) + username[-1]


class OracleClient:
    def __init__(self, config: DataSourceConfig, logger=None, source_name: str | None = None) -> None:
        self.config = config
        self.source_name = source_name or config.name
        self.logger = logger
        self._connection = None

    def __enter__(self) -> "OracleClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def dsn(self) -> str:
        return f"{self.config.host}:{self.config.port}/{self.config.service_name}"

    @property
    def datasource_info(self) -> str:
        return f"{self.source_name}@{self.dsn}"

    @property
    def safe_connection_details(self) -> str:
        return (
            f"source={self.source_name}, host={self.config.host}, port={self.config.port}, "
            f"service_name={self.config.service_name}, username={_mask_username(self.config.username)}, "
            f"password_set={bool(self.config.password)}, "
            f"password_digest={short_sha256(self.config.password) if self.config.password else ''}"
        )

    @staticmethod
    def explain_oracle_error(exc: Exception) -> str:
        message = str(exc)
        hints = [hint for code, hint in _ORACLE_ERROR_HINTS.items() if code in message]
        if hints:
            return " ".join(hints)
        return ""

    def _enable_thick_mode(self, oracledb) -> None:
        global _THICK_MODE_INITIALIZED
        if _THICK_MODE_INITIALIZED:
            return

        system = platform.system()
        client_lib_dir = self.config.client_lib_dir

        try:
            if system == "Linux":
                if client_lib_dir:
                    ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
                    configured_paths = [path for path in ld_library_path.split(os.pathsep) if path]
                    if client_lib_dir not in configured_paths:
                        raise OracleClientError(
                            "Linux thick mode requires LD_LIBRARY_PATH to include "
                            f"{client_lib_dir} before Python starts. Run: "
                            f"export LD_LIBRARY_PATH={client_lib_dir}:$LD_LIBRARY_PATH"
                        )
                oracledb.init_oracle_client()
            elif client_lib_dir:
                oracledb.init_oracle_client(lib_dir=client_lib_dir)
            else:
                oracledb.init_oracle_client()
            _THICK_MODE_INITIALIZED = True
            if self.logger:
                self.logger.info("Oracle driver initialized in thick mode")
        except OracleClientError:
            raise
        except Exception as exc:
            hint = self.explain_oracle_error(exc)
            raise OracleClientError(
                redact_text(
                    "Failed to initialize Oracle thick mode. Install Oracle Instant Client "
                    "and set ORACLE_CLIENT_LIB_DIR to its directory, or add the client "
                    f"directory to PATH/LD_LIBRARY_PATH. {hint} Original error: {exc}"
                )
            ) from exc

    def connect(self):
        if self._connection is not None:
            return self._connection

        if not self.config.username:
            env_name = self.config.username_env or f"{self.source_name.upper()}_USERNAME"
            raise OracleClientError(
                f"Oracle username is empty. Set {env_name} in .env or config.yaml."
            )
        if not self.config.password:
            env_name = self.config.password_env or f"{self.source_name.upper()}_PASSWORD"
            raise OracleClientError(
                f"Oracle password is empty. Set {env_name} in .env or config.yaml."
            )

        try:
            import oracledb
        except ImportError as exc:
            raise OracleClientError(
                "Python package 'oracledb' is not installed. Run: pip install -r requirements.txt"
            ) from exc

        try:
            if self.config.mode == "thick":
                self._enable_thick_mode(oracledb)

            self._connection = oracledb.connect(
                user=self.config.username,
                password=self.config.password,
                dsn=self.dsn,
            )
            if self.logger:
                self.logger.info(
                    "Connected to Oracle datasource %s using %s mode (%s)",
                    self.datasource_info,
                    self.config.mode,
                    self.safe_connection_details,
                )
            return self._connection
        except Exception as exc:  # Oracle errors vary by installed driver version.
            hint = self.explain_oracle_error(exc)
            if self.config.mode == "thin" and "DPY-3010" in str(exc):
                hint = _ORACLE_ERROR_HINTS["DPY-3010"]
            raise OracleClientError(
                redact_text(
                    f"Failed to connect to Oracle datasource {self.datasource_info} "
                    f"({self.safe_connection_details}). {hint} Original error: {exc}"
                )
            ) from exc

    def close(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.close()
        finally:
            self._connection = None

    def test_connection(self) -> bool:
        self.query("select 1 as ok from dual")
        if self.logger:
            self.logger.info("Test query succeeded: select 1 as ok from dual")
        return True

    def query(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        connection = self.connect()
        try:
            return pd.read_sql_query(sql, con=connection, params=params or {})
        except Exception as exc:
            hint = self.explain_oracle_error(exc)
            raise OracleClientError(redact_text(f"Oracle query failed. {hint} Original error: {exc}")) from exc

    def query_sql_file(
        self,
        sql_file: str | Path,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        path = Path(sql_file)
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {path}")

        sql = path.read_text(encoding="utf-8")
        return self.query(sql, params=params)
