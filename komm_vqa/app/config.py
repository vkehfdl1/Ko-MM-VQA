"""App configuration and settings management."""

import os
from pathlib import Path

import streamlit as st

# Default values
DEFAULT_PDF_STORAGE_PATH = "./data/pdfs"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = "5432"
DEFAULT_DB_NAME = "testdb"
DEFAULT_DB_USER = "postgres"


def get_pdf_storage_path() -> Path:
    """Get the PDF storage path from session state or default."""
    path_str = st.session_state.get("pdf_storage_path", DEFAULT_PDF_STORAGE_PATH)
    path = Path(path_str)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_config() -> dict[str, str]:
    """Get database configuration from session state, secrets, or environment."""
    # Priority: session_state > secrets > environment > defaults
    config = {
        "host": DEFAULT_DB_HOST,
        "port": DEFAULT_DB_PORT,
        "database": DEFAULT_DB_NAME,
        "user": DEFAULT_DB_USER,
        "password": "",
    }

    # Try environment variables
    config["host"] = os.environ.get("POSTGRES_HOST", config["host"])
    config["port"] = os.environ.get("POSTGRES_PORT", config["port"])
    config["database"] = os.environ.get("POSTGRES_DB", os.environ.get("TEST_DB_NAME", config["database"]))
    config["user"] = os.environ.get("POSTGRES_USER", config["user"])
    config["password"] = os.environ.get("POSTGRES_PASSWORD", config["password"])

    # Try Streamlit secrets
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        secrets = st.secrets["postgres"]
        config["host"] = secrets.get("host", config["host"])
        config["port"] = str(secrets.get("port", config["port"]))
        config["database"] = secrets.get("database", config["database"])
        config["user"] = secrets.get("user", config["user"])
        config["password"] = secrets.get("password", config["password"])

    # Override with session state if set
    if "db_config" in st.session_state:
        config.update(st.session_state.db_config)

    return config


def render_settings_sidebar() -> None:
    """Render settings in sidebar."""
    with st.sidebar.expander("Settings", expanded=False):
        st.subheader("PDF Storage")
        pdf_path = st.text_input(
            "PDF Storage Path",
            value=st.session_state.get("pdf_storage_path", DEFAULT_PDF_STORAGE_PATH),
            help="Directory where PDF files will be stored",
        )
        st.session_state.pdf_storage_path = pdf_path

        st.subheader("Database")
        db_config = get_db_config()

        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("Host", value=db_config["host"])
            database = st.text_input("Database", value=db_config["database"])
        with col2:
            port = st.text_input("Port", value=db_config["port"])
            user = st.text_input("User", value=db_config["user"])

        password = st.text_input("Password", value=db_config["password"], type="password")

        if st.button("Update DB Config"):
            st.session_state.db_config = {
                "host": host,
                "port": port,
                "database": database,
                "user": user,
                "password": password,
            }
            # Clear cached resources to reconnect
            st.cache_resource.clear()
            st.success("Database configuration updated!")
            st.rerun()
