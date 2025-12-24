"""Image viewer component with caching for thumbnails."""

from io import BytesIO

import streamlit as st
from PIL import Image

from komm_vqa.app.db import get_service


@st.cache_data(ttl=3600, max_entries=500)
def load_thumbnail(page_id: str, size: tuple[int, int] = (200, 200)) -> bytes | None:
    """Load and cache page thumbnail.

    Args:
        page_id: Page ID (used as cache key)
        size: Maximum thumbnail size (width, height)

    Returns:
        PNG image bytes or None if not found
    """
    service = get_service()
    with service._create_uow() as uow:
        page = uow.pages.get_by_id(page_id)
        if page and page.image_contents:
            try:
                img = Image.open(BytesIO(page.image_contents))
                img.thumbnail(size, Image.Resampling.LANCZOS)
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception:
                return None
    return None


@st.cache_data(ttl=300, max_entries=50)
def load_full_image(page_id: str) -> bytes | None:
    """Load and cache full page image.

    Args:
        page_id: Page ID (used as cache key)

    Returns:
        Image bytes or None if not found
    """
    service = get_service()
    with service._create_uow() as uow:
        page = uow.pages.get_by_id(page_id)
        if page and page.image_contents:
            return page.image_contents
    return None


def render_page_thumbnail(page_id: str, page_num: int, size: tuple[int, int] = (200, 200)) -> None:
    """Render a single page thumbnail with caption.

    Args:
        page_id: Page ID
        page_num: Page number for caption
        size: Thumbnail size
    """
    thumb = load_thumbnail(page_id, size)
    if thumb:
        st.image(thumb, caption=f"Page {page_num}", width="stretch")
    else:
        st.warning(f"Page {page_num}: No image")


def render_page_gallery(
    pages: list,
    columns: int = 4,
    selectable: bool = False,
    selected_ids: set[str] | None = None,
) -> list[str]:
    """Render page gallery with optional selection.

    Args:
        pages: List of Page objects
        columns: Number of columns in gallery
        selectable: Whether to show checkboxes for selection
        selected_ids: Set of pre-selected page IDs

    Returns:
        List of selected page IDs (if selectable=True)
    """
    if selected_ids is None:
        selected_ids = set()

    selected = []
    cols = st.columns(columns)

    for i, page in enumerate(pages):
        with cols[i % columns]:
            thumb = load_thumbnail(page.id)
            if thumb:
                st.image(thumb, width="stretch")
            else:
                st.info(f"Page {page.page_num}")

            if selectable:
                is_selected = st.checkbox(
                    f"Page {page.page_num}",
                    value=page.id in selected_ids,
                    key=f"page_select_{page.id}",
                )
                if is_selected:
                    selected.append(page.id)
            else:
                st.caption(f"Page {page.page_num}")

    return selected


def render_document_gallery(document_id: str, columns: int = 4) -> None:
    """Render all pages of a document as a gallery.

    Args:
        document_id: Document ID
        columns: Number of columns
    """
    service = get_service()
    with service._create_uow() as uow:
        pages = uow.pages.get_by_document_id(document_id)

    if not pages:
        st.info("No pages found for this document")
        return

    render_page_gallery(pages, columns=columns)


def render_image_modal(page_id: str, page_num: int) -> None:
    """Render a modal/dialog for full-size image view.

    Args:
        page_id: Page ID
        page_num: Page number for title
    """
    img_bytes = load_full_image(page_id)
    if img_bytes:
        st.image(img_bytes, caption=f"Page {page_num} (Full Size)")
    else:
        st.error("Could not load image")


@st.dialog("Full Size Image", width="large")
def show_full_image_dialog(page_id: str, page_num: int) -> None:
    """Show full-size image in a dialog.

    Args:
        page_id: Page ID
        page_num: Page number for title
    """
    img_bytes = load_full_image(page_id)
    if img_bytes:
        # Show image info
        img = Image.open(BytesIO(img_bytes))
        st.caption(f"Page {page_num} | Size: {img.width} x {img.height} px")
        st.image(img_bytes, width="stretch")
    else:
        st.error("Could not load image")
