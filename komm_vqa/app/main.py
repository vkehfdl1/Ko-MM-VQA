"""VQA Dataset Creator - Main entry point for Streamlit app.

Run with: streamlit run autorag_research/app/main.py
"""

import streamlit as st

st.set_page_config(
    page_title="VQA Dataset Creator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Main application entry point."""
    st.title("VQA Dataset Creator")
    st.write("Create Multi-Page Multi-Hop Visual Question Answering datasets")

    # Import here to avoid circular imports
    from komm_vqa.app.config import render_settings_sidebar
    from komm_vqa.app.db import check_db_connection, get_service

    # Render settings in sidebar
    render_settings_sidebar()

    # Check database connection
    is_connected, message = check_db_connection()

    if is_connected:
        st.sidebar.success("DB Connected")

        # Display statistics
        try:
            service = get_service()
            stats = service.get_statistics()

            st.subheader("Dataset Statistics")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Documents", stats.get("documents", 0))
            with col2:
                st.metric("Pages", stats.get("pages", 0))
            with col3:
                image_chunks = stats.get("image_chunks", {})
                if isinstance(image_chunks, dict):
                    st.metric("Image Chunks", image_chunks.get("total", 0))
                else:
                    st.metric("Image Chunks", image_chunks)
            with col4:
                st.metric("Queries", stats.get("queries", 0))

            st.divider()

            st.info(
                """
                **How to use:**
                1. **File Management**: Upload PDF files and view pages
                2. **QA Creation**: Select pages and create queries with retrieval ground truth
                3. **Data Browser**: View and manage existing queries

                Use the sidebar to navigate between pages.
                """
            )

        except Exception as e:
            st.error(f"Error loading statistics: {e}")

    else:
        st.sidebar.error("DB Disconnected")
        st.error(f"Database connection failed: {message}")
        st.info(
            """
            Please configure your database connection in the Settings sidebar.

            You can also set environment variables:
            - `POSTGRES_HOST`
            - `POSTGRES_PORT`
            - `POSTGRES_DB` or `TEST_DB_NAME`
            - `POSTGRES_USER`
            - `POSTGRES_PASSWORD`

            Or create a `.streamlit/secrets.toml` file with:
            ```toml
            [postgres]
            host = "localhost"
            port = 5432
            database = "testdb"
            user = "postgres"
            password = "your_password"
            ```
            """
        )


if __name__ == "__main__":
    main()
