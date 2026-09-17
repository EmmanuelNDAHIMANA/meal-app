"""SQLAlchemy engine (pymysql driver) + small query helpers."""
from __future__ import annotations
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import config

_ENGINE: Engine | None = None


def get_engine() -> Engine:
    """Cached engine. Works both inside Streamlit and in plain scripts."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    if not config.DB_PASSWORD:
        raise RuntimeError(
            "DB_PASSWORD is empty. Create .streamlit/secrets.toml (copy from "
            "secrets.toml.example) or export DB_PASSWORD, then run again from "
            "the project folder."
        )

    uri = (
        f"mysql+pymysql://{config.DB_USER}:{urllib.parse.quote_plus(config.DB_PASSWORD)}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}?charset=utf8mb4"
    )
    _ENGINE = create_engine(
        uri,
        pool_pre_ping=True,
        pool_recycle=280,
        connect_args={"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30},
    )
    return _ENGINE


def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def execute(sql: str, params: dict | None = None):
    with get_engine().begin() as conn:
        conn.execute(text(sql), params or {})


def insert_dataframe(df: pd.DataFrame, table: str, chunksize: int = 500):
    with get_engine().begin() as conn:
        df.to_sql(table, conn, if_exists="append", index=False, chunksize=chunksize)


def test_connection() -> tuple[bool, str]:
    try:
        run_query("SELECT 1 AS ok")
        return True, "Connected"
    except Exception as e:
        return False, str(e)
