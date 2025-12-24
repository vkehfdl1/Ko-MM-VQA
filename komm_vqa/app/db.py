"""Database connection management for Streamlit app."""

from collections.abc import Callable

import streamlit as st
from autorag_research.app.config import get_db_config
from autorag_research.orm.schema_factory import create_schema
from autorag_research.orm.service.multi_modal_ingestion import MultiModalIngestionService
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def get_db_url() -> str:
    """Construct database URL from configuration."""
    config = get_db_config()
    return f"postgresql+psycopg://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"


@st.cache_resource
def get_engine() -> Engine:
    """Get cached database engine (singleton per Streamlit session)."""
    return create_engine(
        get_db_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@st.cache_resource
def get_session_factory() -> Callable[[], Session]:
    """Get cached sessionmaker factory."""
    return sessionmaker(bind=get_engine())


@st.cache_resource
def get_schema():
    """Get schema with string primary keys for UUID support."""
    return create_schema(768, primary_key_type="string")


def get_service() -> MultiModalIngestionService:
    """Get MultiModalIngestionService instance.

    Note: This is not cached because the service holds references to
    session factory and schema which should be fresh per request.
    """
    return MultiModalIngestionService(get_session_factory(), get_schema())


def check_db_connection() -> tuple[bool, str]:
    """Check database connection status.

    Returns:
        Tuple of (is_connected, message)
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        return False, str(e)
    else:
        return True, "Connected"
