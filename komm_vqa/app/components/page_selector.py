"""Page selector component for multi-document page selection."""

import streamlit as st

from komm_vqa.app.components.image_viewer import load_thumbnail
from komm_vqa.app.db import get_service


def get_all_documents() -> list:
    """Get all documents from database.

    Returns:
        List of Document objects
    """
    service = get_service()
    with service._create_uow() as uow:
        return uow.documents.get_all()


def get_pages_for_document(document_id: str) -> list:
    """Get all pages for a document.

    Args:
        document_id: Document ID

    Returns:
        List of Page objects
    """
    service = get_service()
    with service._create_uow() as uow:
        return uow.pages.get_by_document_id(document_id)


def get_image_chunk_for_page(page_id: str) -> str | None:
    """Get ImageChunk ID for a page.

    Args:
        page_id: Page ID

    Returns:
        ImageChunk ID or None
    """
    service = get_service()
    with service._create_uow() as uow:
        image_chunks = uow.image_chunks.get_by_page_id(page_id)
        if image_chunks:
            return image_chunks[0].id
    return None


def _get_image_chunk_ids_for_pages(page_ids: set[str]) -> list[str]:
    """Get ImageChunk IDs for a set of page IDs."""
    image_chunk_ids = []
    for page_id in page_ids:
        ic_id = get_image_chunk_for_page(page_id)
        if ic_id:
            image_chunk_ids.append(ic_id)
    return image_chunk_ids


def _render_page_with_checkbox(
    page,
    selected_pages: set[str],
    key_prefix: str,
) -> bool:
    """Render a single page with checkbox and return selection state."""
    thumb = load_thumbnail(page.id, (180, 180))
    if thumb:
        st.image(thumb, use_container_width=True)
    else:
        st.info(f"Page {page.page_num}")

    return st.checkbox(
        f"Page {page.page_num}",
        value=page.id in selected_pages,
        key=f"{key_prefix}_page_{page.id}",
    )


def page_multi_selector(
    key_prefix: str = "page_selector",
    columns: int = 4,
) -> tuple[list[str], list[str]]:
    """Multi-document page selector with image previews.

    Args:
        key_prefix: Unique prefix for widget keys
        columns: Number of columns for gallery

    Returns:
        Tuple of (selected_page_ids, selected_image_chunk_ids)
    """
    # Initialize session state for selections
    if f"{key_prefix}_selected_pages" not in st.session_state:
        st.session_state[f"{key_prefix}_selected_pages"] = set()

    selected_pages: set[str] = st.session_state[f"{key_prefix}_selected_pages"]

    # Document selection
    documents = get_all_documents()

    if not documents:
        st.warning("No documents found. Please upload PDFs first.")
        return [], []

    doc_options = {f"{d.title or d.filename or 'Untitled'} ({d.id[:8]}...)": d.id for d in documents}

    selected_doc_name = st.selectbox(
        "Select Document",
        options=["", *list(doc_options.keys())],
        key=f"{key_prefix}_doc_select",
    )

    if not selected_doc_name:
        if selected_pages:
            st.write(f"**Currently selected:** {len(selected_pages)} page(s)")
        return list(selected_pages), []

    doc_id = doc_options[selected_doc_name]
    pages = get_pages_for_document(doc_id)

    if not pages:
        st.info("No pages found for this document")
        return list(selected_pages), []

    st.write("**Select pages (click to toggle):**")
    cols = st.columns(columns)

    for i, page in enumerate(pages):
        with cols[i % columns]:
            is_selected = _render_page_with_checkbox(page, selected_pages, key_prefix)

            if is_selected:
                selected_pages.add(page.id)
            else:
                selected_pages.discard(page.id)

    st.session_state[f"{key_prefix}_selected_pages"] = selected_pages

    st.divider()
    st.write(f"**Selected pages:** {len(selected_pages)}")

    if selected_pages:
        return list(selected_pages), _get_image_chunk_ids_for_pages(selected_pages)

    return [], []


def clear_page_selection(key_prefix: str = "page_selector") -> None:
    """Clear all page selections.

    Args:
        key_prefix: The key prefix used in page_multi_selector
    """
    st.session_state[f"{key_prefix}_selected_pages"] = set()


def render_selected_pages_preview(
    page_ids: list[str],
    columns: int = 6,
) -> None:
    """Render preview of selected pages.

    Args:
        page_ids: List of selected page IDs
        columns: Number of columns
    """
    if not page_ids:
        st.info("No pages selected")
        return

    service = get_service()
    cols = st.columns(min(len(page_ids), columns))

    for i, page_id in enumerate(page_ids[:columns]):
        with cols[i]:
            thumb = load_thumbnail(page_id, (120, 120))
            if thumb:
                st.image(thumb, use_container_width=True)

            # Get page info
            with service._create_uow() as uow:
                page = uow.pages.get_by_id(page_id)
                if page:
                    st.caption(f"P{page.page_num}")

    if len(page_ids) > columns:
        st.caption(f"... and {len(page_ids) - columns} more")
