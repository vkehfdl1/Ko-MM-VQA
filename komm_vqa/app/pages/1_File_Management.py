"""File Management page - Upload PDFs and browse documents."""

import uuid
from io import BytesIO

import streamlit as st
from pdf2image import convert_from_bytes
from pdf2image.pdf2image import pdfinfo_from_bytes

from komm_vqa.app.components.image_viewer import load_thumbnail
from komm_vqa.app.config import get_pdf_storage_path, render_settings_sidebar
from komm_vqa.app.db import check_db_connection, get_service

st.set_page_config(page_title="File Management", page_icon="📁", layout="wide")
st.title("📁 File Management")

# Render settings sidebar
render_settings_sidebar()

# Check connection
is_connected, message = check_db_connection()
if not is_connected:
    st.error(f"Database not connected: {message}")
    st.stop()


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

    # Convert PDF pages to images
    pdf_bytes = uploaded_file.getvalue()
    images = convert_pdf_with_progress(pdf_bytes)

    st.info(f"Processing {len(images)} pages...")

    # Add File
    file_ids = service.add_files([{"path": str(save_path), "file_type": "raw"}])
    file_id = file_ids[0]

    # Add Document (1:1 with File)
    doc_ids = service.add_documents([
        {
            "path": file_id,
            "filename": filename,
            "title": filename.replace(".pdf", ""),
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
                "image_content": img_bytes,
                "mimetype": "image/png",
            }
        ])
        page_id = page_ids[0]

        # Add ImageChunk (1:1 with Page)
        service.add_image_chunks([
            {
                "content": img_bytes,
                "mimetype": "image/png",
                "parent_page_id": page_id,
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
            # Delete from DB (cascade will handle pages, image_chunks)
            uow.documents.delete_by_id(document_id)
            uow.commit()

            # Optionally delete physical file
            # (commented out for safety - user can manually delete)
            # if doc.file and doc.file.path:
            #     Path(doc.file.path).unlink(missing_ok=True)


# Main content
tab1, tab2 = st.tabs(["📤 Upload PDF", "📂 Browse Documents"])

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
    st.subheader("Browse Documents")

    service = get_service()

    # Get all documents
    with service._create_uow() as uow:
        documents = uow.documents.get_all()

    if not documents:
        st.info("No documents found. Upload a PDF to get started.")
    else:
        st.write(f"**Total Documents:** {len(documents)}")

        for doc in documents:
            with st.expander(f"📄 {doc.title or doc.filename or 'Untitled'} (ID: {doc.id[:8]}...)"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**Filename:** {doc.filename}")
                    st.write(f"**Title:** {doc.title}")
                    if doc.file:
                        st.write(f"**Path:** {doc.file.path}")

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{doc.id}", type="secondary"):
                        delete_document(doc.id)
                        st.success("Document deleted!")
                        st.cache_data.clear()
                        st.rerun()

                # Show pages
                st.write("**Pages:**")
                with service._create_uow() as uow:
                    pages = uow.pages.get_by_document_id(doc.id)

                if pages:
                    # Show thumbnails in a grid
                    cols = st.columns(min(len(pages), 6))
                    for i, page in enumerate(pages[:12]):  # Limit to first 12
                        with cols[i % 6]:
                            thumb = load_thumbnail(page.id, (150, 150))
                            if thumb:
                                st.image(thumb, caption=f"P{page.page_num}")

                    if len(pages) > 12:
                        st.caption(f"... and {len(pages) - 12} more pages")
                else:
                    st.info("No pages")
