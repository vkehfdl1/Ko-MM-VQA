"""File Management page - Upload PDFs and browse documents."""

import base64
import uuid
from io import BytesIO
from pathlib import Path

import streamlit as st
from pdf2image import convert_from_bytes
from pdf2image.pdf2image import pdfinfo_from_bytes
from PIL import Image

from komm_vqa.app.components.image_viewer import load_full_image
from komm_vqa.app.config import get_pdf_storage_path, render_settings_sidebar
from komm_vqa.app.db import check_db_connection, get_service


def render_pdf_viewer(pdf_path: str, height: int = 800) -> None:
    """Render PDF viewer using iframe with base64 encoded PDF.

    Args:
        pdf_path: Path to PDF file
        height: Height of the viewer in pixels
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        st.error(f"PDF file not found: {pdf_path}")
        return

    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()

    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="{height}px"
            type="application/pdf"
            style="border: 1px solid #ddd; border-radius: 4px;"
        >
        </iframe>
    '''
    st.markdown(pdf_display, unsafe_allow_html=True)


st.set_page_config(page_title="File Management", page_icon="📁", layout="wide")
st.title("📁 File Management")

# Render settings sidebar
render_settings_sidebar()

# Check connection
is_connected, message = check_db_connection()
if not is_connected:
    st.error(f"Database not connected: {message}")
    st.stop()


def convert_images_to_pdf(uploaded_images: list) -> tuple[bytes, str]:
    """Convert multiple uploaded images to a single PDF.

    Args:
        uploaded_images: List of Streamlit UploadedFile objects (images)

    Returns:
        Tuple of (pdf_bytes, suggested_filename)
    """
    if not uploaded_images:
        raise ValueError("No images provided")

    progress_bar = st.progress(0)
    status_text = st.empty()

    pil_images = []
    for i, img_file in enumerate(uploaded_images):
        status_text.text(f"Loading image {i + 1}/{len(uploaded_images)}...")
        img = Image.open(img_file)
        # Convert to RGB if necessary (for PNG with alpha channel, etc.)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        pil_images.append(img)
        progress_bar.progress((i + 1) / len(uploaded_images))

    status_text.text("Creating PDF...")

    # Create PDF from images
    pdf_buffer = BytesIO()
    if len(pil_images) == 1:
        pil_images[0].save(pdf_buffer, format="PDF")
    else:
        pil_images[0].save(
            pdf_buffer,
            format="PDF",
            save_all=True,
            append_images=pil_images[1:],
        )

    pdf_bytes = pdf_buffer.getvalue()

    status_text.text("PDF created successfully!")
    progress_bar.empty()

    # Generate filename from first image
    first_name = Path(uploaded_images[0].name).stem
    suggested_filename = f"{first_name}_combined.pdf"

    return pdf_bytes, suggested_filename


def convert_pdf_with_progress(pdf_bytes: bytes) -> list:
    """Convert PDF to images with progress indication.

    Args:
        pdf_bytes: PDF file bytes

    Returns:
        List of PIL Image objects
    """
    # Get page count
    try:
        info = pdfinfo_from_bytes(pdf_bytes)
        total_pages = info["Pages"]
    except Exception:
        # Fallback: convert all at once
        return convert_from_bytes(pdf_bytes, dpi=150, fmt="PNG")

    progress_bar = st.progress(0)
    status_text = st.empty()

    images = []
    for i in range(1, total_pages + 1):
        status_text.text(f"Converting page {i}/{total_pages}...")
        page_images = convert_from_bytes(
            pdf_bytes,
            dpi=150,
            first_page=i,
            last_page=i,
            fmt="PNG",
        )
        images.extend(page_images)
        progress_bar.progress(i / total_pages)

    status_text.text("Conversion complete!")
    progress_bar.empty()
    return images


def upload_pdf(uploaded_file) -> tuple[str, int]:
    """Process uploaded PDF file.

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        Tuple of (document_id, page_count)
    """
    service = get_service()
    storage_path = get_pdf_storage_path()

    # Generate unique filename
    file_uuid = str(uuid.uuid4())
    filename = uploaded_file.name
    save_path = storage_path / f"{file_uuid}_{filename}"

    # Save PDF to filesystem
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Add File
    file_ids = service.add_files([{"path": str(save_path), "type": "raw"}])
    file_id = file_ids[0]

    # Convert PDF pages to images
    pdf_bytes = uploaded_file.getvalue()
    images = convert_pdf_with_progress(pdf_bytes)

    st.info(f"Processing {len(images)} pages...")

    # Add Document (1:1 with File)
    doc_ids = service.add_documents([
        {
            "path": file_id,
            "filename": filename,
            "title": filename.split(".")[0].strip(),
        }
    ])
    doc_id = doc_ids[0]

    # Add Pages and ImageChunks
    for page_num, img in enumerate(images, start=1):
        # Convert PIL image to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        # Add Page
        page_ids = service.add_pages([
            {
                "document_id": doc_id,
                "page_num": page_num,
                "image_contents": img_bytes,
                "mimetype": "image/png",
            }
        ])
        page_id = page_ids[0]

        # Add ImageChunk (1:1 with Page)
        service.add_image_chunks([
            {
                "contents": img_bytes,
                "mimetype": "image/png",
                "parent_page": page_id,
            }
        ])

    return doc_id, len(images)


def upload_images_as_pdf(uploaded_images: list, doc_title: str | None = None) -> tuple[str, int]:
    """Process multiple uploaded images as a single PDF document.

    Args:
        uploaded_images: List of Streamlit UploadedFile objects (images)
        doc_title: Optional document title

    Returns:
        Tuple of (document_id, page_count)
    """
    # Convert images to PDF
    pdf_bytes, suggested_filename = convert_images_to_pdf(uploaded_images)

    service = get_service()
    storage_path = get_pdf_storage_path()

    # Generate unique filename
    file_uuid = str(uuid.uuid4())
    filename = doc_title + ".pdf" if doc_title else suggested_filename
    save_path = storage_path / f"{file_uuid}_{filename}"

    # Save PDF to filesystem
    with open(save_path, "wb") as f:
        f.write(pdf_bytes)

    # Add File
    file_ids = service.add_files([{"path": str(save_path), "type": "raw"}])
    file_id = file_ids[0]

    # Convert PDF pages to images (re-convert for consistent quality)
    images = convert_pdf_with_progress(pdf_bytes)

    st.info(f"Processing {len(images)} pages...")

    # Add Document
    doc_ids = service.add_documents([
        {
            "path": file_id,
            "filename": filename,
            "title": doc_title or filename.split(".")[0].strip(),
        }
    ])
    doc_id = doc_ids[0]

    # Add Pages and ImageChunks
    for page_num, img in enumerate(images, start=1):
        # Convert PIL image to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        # Add Page
        page_ids = service.add_pages([
            {
                "document_id": doc_id,
                "page_num": page_num,
                "image_contents": img_bytes,
                "mimetype": "image/png",
            }
        ])
        page_id = page_ids[0]

        # Add ImageChunk (1:1 with Page)
        service.add_image_chunks([
            {
                "contents": img_bytes,
                "mimetype": "image/png",
                "parent_page": page_id,
            }
        ])

    return doc_id, len(images)


def delete_document(document_id: str) -> None:
    """Delete a document and all related data.

    Args:
        document_id: Document ID to delete
    """
    service = get_service()
    with service._create_uow() as uow:
        # Get document to find file path
        doc = uow.documents.get_by_id(document_id)
        if doc:
            file_id = doc.path  # File ID referenced by Document

            # Get all pages for this document
            pages = uow.pages.get_by_document_id(document_id)

            # Delete ImageChunks and Captions for each page first (FK constraint)
            for page in pages:
                # Delete ImageChunks
                image_chunks = uow.image_chunks.get_by_page_id(page.id)
                for ic in image_chunks:
                    uow.image_chunks.delete_by_id(ic.id)

                # Delete Captions (if any)
                if hasattr(uow, "captions"):
                    captions = uow.captions.get_by_page_id(page.id)
                    for caption in captions:
                        uow.captions.delete_by_id(caption.id)

            # Delete Pages (FK constraint)
            for page in pages:
                uow.pages.delete_by_id(page.id)

            # Delete Document
            uow.documents.delete_by_id(document_id)

            # Delete File (orphan after Document deletion)
            if file_id:
                uow.files.delete_by_id(file_id)

            uow.commit()


# Main content
tab1, tab2, tab3 = st.tabs(["📤 Upload PDF", "📷 Upload Images", "📂 Browse Documents"])

with tab1:
    st.subheader("Upload PDF File")

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Upload a PDF file to convert to pages and image chunks",
    )

    if uploaded_file is not None:
        st.write(f"**File:** {uploaded_file.name}")
        st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")

        if st.button("Process PDF", type="primary"):
            with st.spinner("Processing..."):
                try:
                    doc_id, page_count = upload_pdf(uploaded_file)
                    st.success(f"Successfully processed! Document ID: {doc_id[:8]}..., {page_count} pages")
                    st.cache_data.clear()  # Clear cache to show new data
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing PDF: {e}")

with tab2:
    st.subheader("Upload Images as PDF")
    st.write("Upload multiple images to combine them into a single PDF document.")

    uploaded_images = st.file_uploader(
        "Choose image files",
        type=["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        accept_multiple_files=True,
        help="Upload multiple images to combine into a PDF. Images will be ordered by filename.",
    )

    if uploaded_images:
        # Sort by filename for consistent ordering
        uploaded_images = sorted(uploaded_images, key=lambda x: x.name)

        st.write(f"**Selected images:** {len(uploaded_images)}")

        # Document title input
        doc_title = st.text_input(
            "Document title (optional)",
            placeholder="Enter a title for the combined document",
            help="If not provided, the first image's filename will be used",
        )

        # Preview images
        with st.expander("Preview images (sorted by filename)", expanded=False):
            cols = st.columns(4)
            for i, img_file in enumerate(uploaded_images):
                with cols[i % 4]:
                    st.image(img_file, caption=f"{i + 1}. {img_file.name}", width="stretch")

        if st.button("Create PDF and Process", type="primary", key="process_images"):
            with st.spinner("Processing..."):
                try:
                    doc_id, page_count = upload_images_as_pdf(
                        uploaded_images,
                        doc_title=doc_title.strip() if doc_title and doc_title.strip() else None,
                    )
                    st.success(f"Successfully processed! Document ID: {doc_id[:8]}..., {page_count} pages")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing images: {e}")

with tab3:
    st.subheader("Browse Documents")

    service = get_service()

    # Get all documents with related data
    with service._create_uow() as uow:
        documents = uow.documents.get_all()
        # Extract data while session is active to avoid DetachedInstanceError
        doc_list = []
        for doc in documents:
            pages = uow.pages.get_by_document_id(doc.id)
            doc_list.append({
                "id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
                "file_path": doc.file.path if doc.file else None,
                "page_count": len(pages),
            })

    if not doc_list:
        st.info("No documents found. Upload a PDF to get started.")
    else:
        # Document selector
        doc_options = {f"{d['title'] or d['filename'] or 'Untitled'} ({d['page_count']} pages)": d for d in doc_list}

        selected_doc_name = st.selectbox(
            "Select Document",
            options=list(doc_options.keys()),
            key="browse_doc_select",
        )

        if selected_doc_name:
            doc_info = doc_options[selected_doc_name]

            # Document info and delete button
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**Document ID:** `{doc_info['id'][:8]}...`")
                st.write(f"**Pages:** {doc_info['page_count']}")
            with col2:
                if st.button("🗑️ Delete Document", type="secondary"):
                    delete_document(doc_info["id"])
                    st.success("Document deleted!")
                    st.cache_data.clear()
                    st.rerun()

            st.divider()

            # View mode selector
            view_mode = st.radio(
                "View Mode",
                options=["PDF Viewer", "Page by Number"],
                horizontal=True,
                key="browse_view_mode",
            )

            if view_mode == "PDF Viewer":
                # PDF Viewer
                if doc_info["file_path"]:
                    st.write("**PDF Preview:**")
                    render_pdf_viewer(doc_info["file_path"], height=700)
                else:
                    st.warning("PDF file path not available")

            else:  # Page by Number
                st.write("**View Page by Number:**")
                col1, col2 = st.columns([3, 1])
                with col1:
                    page_num = st.number_input(
                        "Page number",
                        min_value=1,
                        max_value=doc_info["page_count"],
                        value=1,
                        step=1,
                        key="browse_page_num",
                    )

                # Get and display the page
                with service._create_uow() as uow:
                    pages = uow.pages.get_by_document_id(doc_info["id"])
                    page_info = None
                    for p in pages:
                        if p.page_num == page_num:
                            page_info = {"id": p.id, "page_num": p.page_num}
                            break

                if page_info:
                    st.write(f"**Page {page_num}:**")
                    img_bytes = load_full_image(page_info["id"])
                    if img_bytes:
                        st.image(img_bytes, width="stretch")
                    else:
                        st.warning("Could not load image")
                else:
                    st.error(f"Page {page_num} not found")
