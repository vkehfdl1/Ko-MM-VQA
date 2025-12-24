"""Page selector component for multi-document page selection by page number."""

import streamlit as st

from komm_vqa.app.components.image_viewer import load_full_image
from komm_vqa.app.db import get_service


def get_all_documents_info() -> list[dict]:
    """Get all documents info from database.

    Returns:
        List of document info dicts with id, title, filename, page_count
    """
    service = get_service()
    with service._create_uow() as uow:
        documents = uow.documents.get_all()
        doc_list = []
        for doc in documents:
            pages = uow.pages.get_by_document_id(doc.id)
            doc_list.append({
                "id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
                "page_count": len(pages),
            })
        return doc_list


def get_page_by_number(document_id: str, page_num: int) -> dict | None:
    """Get page info by document ID and page number.

    Args:
        document_id: Document ID
        page_num: Page number (1-based)

    Returns:
        Page info dict or None if not found
    """
    service = get_service()
    with service._create_uow() as uow:
        pages = uow.pages.get_by_document_id(document_id)
        for page in pages:
            if page.page_num == page_num:
                # Get image chunk ID
                image_chunks = uow.image_chunks.get_by_page_id(page.id)
                image_chunk_id = image_chunks[0].id if image_chunks else None
                return {
                    "id": page.id,
                    "page_num": page.page_num,
                    "image_chunk_id": image_chunk_id,
                }
    return None


def page_number_selector(
    key_prefix: str = "page_selector",
) -> tuple[list[str], list[str]]:
    """Page selector using page number input.

    Args:
        key_prefix: Unique prefix for widget keys

    Returns:
        Tuple of (selected_page_ids, selected_image_chunk_ids)
    """
    # Initialize session state for selections
    if f"{key_prefix}_selected_pages" not in st.session_state:
        st.session_state[f"{key_prefix}_selected_pages"] = []  # List of {doc_id, page_num, page_id, image_chunk_id}

    selected_pages: list[dict] = st.session_state[f"{key_prefix}_selected_pages"]

    # Get documents
    documents = get_all_documents_info()

    if not documents:
        st.warning("No documents found. Please upload PDFs first.")
        return [], []

    # Document selection
    doc_options = {f"{d['title'] or d['filename'] or 'Untitled'} ({d['page_count']} pages)": d["id"] for d in documents}
    doc_page_counts = {d["id"]: d["page_count"] for d in documents}

    selected_doc_name = st.selectbox(
        "Select Document",
        options=list(doc_options.keys()),
        key=f"{key_prefix}_doc_select",
    )

    if not selected_doc_name:
        return _get_ids_from_selected(selected_pages)

    doc_id = doc_options[selected_doc_name]
    max_pages = doc_page_counts[doc_id]

    # Page number input
    st.write(f"**Total pages in document:** {max_pages}")

    col1, col2 = st.columns([3, 1])
    with col1:
        page_num = st.number_input(
            "Page number",
            min_value=1,
            max_value=max_pages,
            value=1,
            step=1,
            key=f"{key_prefix}_page_num",
        )
    with col2:
        add_clicked = st.button("Add Page", key=f"{key_prefix}_add_btn", type="primary")

    # Preview the page
    st.write("**Preview:**")
    page_info = get_page_by_number(doc_id, page_num)
    if page_info:
        img_bytes = load_full_image(page_info["id"])
        if img_bytes:
            st.image(img_bytes, use_container_width=True)
        else:
            st.warning("Could not load image")

        # Add button action
        if add_clicked:
            # Check if already added
            already_added = any(p["doc_id"] == doc_id and p["page_num"] == page_num for p in selected_pages)
            if already_added:
                st.warning(f"Page {page_num} is already added.")
            else:
                selected_pages.append({
                    "doc_id": doc_id,
                    "doc_name": selected_doc_name,
                    "page_num": page_num,
                    "page_id": page_info["id"],
                    "image_chunk_id": page_info["image_chunk_id"],
                })
                st.session_state[f"{key_prefix}_selected_pages"] = selected_pages
                st.success(f"Added page {page_num}")
                st.rerun()
    else:
        st.error(f"Page {page_num} not found")

    # Show selected pages
    st.divider()
    st.write(f"**Selected pages:** {len(selected_pages)}")

    if selected_pages:
        for i, p in enumerate(selected_pages):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i + 1}. {p['doc_name']} - Page {p['page_num']}")
            with col2:
                if st.button("Remove", key=f"{key_prefix}_remove_{i}"):
                    selected_pages.pop(i)
                    st.session_state[f"{key_prefix}_selected_pages"] = selected_pages
                    st.rerun()

    return _get_ids_from_selected(selected_pages)


def _get_ids_from_selected(selected_pages: list[dict]) -> tuple[list[str], list[str]]:
    """Extract page IDs and image chunk IDs from selected pages."""
    page_ids = [p["page_id"] for p in selected_pages]
    image_chunk_ids = [p["image_chunk_id"] for p in selected_pages if p["image_chunk_id"]]
    return page_ids, image_chunk_ids


def clear_page_selection(key_prefix: str = "page_selector") -> None:
    """Clear all page selections.

    Args:
        key_prefix: The key prefix used in page_number_selector
    """
    st.session_state[f"{key_prefix}_selected_pages"] = []


def render_selected_pages_preview(
    page_ids: list[str],
    columns: int = 4,
) -> None:
    """Render preview of selected pages with full images.

    Args:
        page_ids: List of selected page IDs
        columns: Number of columns
    """
    if not page_ids:
        st.info("No pages selected")
        return

    service = get_service()

    for page_id in page_ids:
        with service._create_uow() as uow:
            page = uow.pages.get_by_id(page_id)
            if page:
                page_num = page.page_num
                doc = page.document
                doc_title = doc.title or doc.filename or "Untitled" if doc else "Unknown"

        with st.expander(f"{doc_title} - Page {page_num}", expanded=False):
            img_bytes = load_full_image(page_id)
            if img_bytes:
                st.image(img_bytes, use_container_width=True)
            else:
                st.warning("Could not load image")
