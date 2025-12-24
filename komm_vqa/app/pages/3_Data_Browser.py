"""Data Browser page - View and manage existing queries."""

import streamlit as st

from komm_vqa.app.components.image_viewer import load_thumbnail
from komm_vqa.app.config import render_settings_sidebar
from komm_vqa.app.db import check_db_connection, get_service

st.set_page_config(page_title="Data Browser", page_icon="📊", layout="wide")
st.title("📊 Data Browser")

# Render settings sidebar
render_settings_sidebar()

# Check connection
is_connected, message = check_db_connection()
if not is_connected:
    st.error(f"Database not connected: {message}")
    st.stop()


def delete_query(query_id: str) -> None:
    """Delete a query and its retrieval relations.

    Args:
        query_id: Query ID to delete
    """
    service = get_service()
    with service._create_uow() as uow:
        # Delete RetrievalRelations first (FK constraint)
        relations = uow.retrieval_relations.get_by_query_id(query_id)
        for rel in relations:
            uow.retrieval_relations.delete(rel)

        # Delete Query
        uow.queries.delete_by_id(query_id)
        uow.commit()


def get_image_chunk_thumbnail(image_chunk_id: str) -> bytes | None:
    """Get thumbnail for an image chunk.

    Args:
        image_chunk_id: ImageChunk ID

    Returns:
        Thumbnail bytes or None
    """
    service = get_service()
    with service._create_uow() as uow:
        image_chunk = uow.image_chunks.get_by_id(image_chunk_id)
        if image_chunk and image_chunk.parent_page:
            # parent_page is FK ID (not object), use directly
            return load_thumbnail(image_chunk.parent_page)
    return None


# Main content
tab1, tab2 = st.tabs(["📝 Queries", "📊 Statistics"])

with tab1:
    st.subheader("All Queries")

    service = get_service()

    # Pagination
    page_size = 10
    if "browser_page" not in st.session_state:
        st.session_state.browser_page = 0

    with service._create_uow() as uow:
        # Get all queries and extract data while session is active
        all_queries = uow.queries.get_all()
        total_queries = len(all_queries)

        # Extract query data for current page
        start_idx = st.session_state.browser_page * page_size
        end_idx = min(start_idx + page_size, total_queries)
        page_queries = all_queries[start_idx:end_idx]

        query_list = []
        for q in page_queries:
            relations = uow.retrieval_relations.get_by_query_id(q.id)
            # Group relations by group_index
            groups: dict[int, list] = {}
            for rel in relations:
                if rel.group_index not in groups:
                    groups[rel.group_index] = []
                groups[rel.group_index].append({
                    "group_index": rel.group_index,
                    "group_order": rel.group_order,
                    "image_chunk_id": rel.image_chunk_id,
                })

            query_list.append({
                "id": q.id,
                "contents": q.contents,
                "query_to_llm": q.query_to_llm,
                "generation_gt": q.generation_gt,
                "relation_groups": groups,
            })

    if total_queries == 0:
        st.info("No queries found. Create queries in the QA Creation page.")
    else:
        # Pagination controls
        total_pages = (total_queries + page_size - 1) // page_size
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if st.button("← Previous", disabled=st.session_state.browser_page == 0):
                st.session_state.browser_page -= 1
                st.rerun()

        with col2:
            st.write(f"Page {st.session_state.browser_page + 1} of {total_pages} ({total_queries} queries)")

        with col3:
            if st.button("Next →", disabled=st.session_state.browser_page >= total_pages - 1):
                st.session_state.browser_page += 1
                st.rerun()

        # Display queries
        for query_info in query_list:
            contents = query_info["contents"]
            with st.expander(
                f"Q: {contents[:60]}..." if len(contents) > 60 else f"Q: {contents}",
                expanded=False,
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**ID:** `{query_info['id']}`")
                    st.write(f"**Query:** {query_info['contents']}")

                    if query_info["query_to_llm"]:
                        st.write(f"**Query to LLM:** {query_info['query_to_llm']}")

                    if query_info["generation_gt"]:
                        st.write("**Generation GT:**")
                        for gt in query_info["generation_gt"]:
                            st.write(f"  - {gt}")

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_query_{query_info['id']}", type="secondary"):
                        delete_query(query_info["id"])
                        st.success("Query deleted!")
                        st.cache_data.clear()
                        st.rerun()

                # Display retrieval relations
                st.divider()
                st.write("**Retrieval Ground Truth:**")

                groups = query_info["relation_groups"]
                if groups:
                    # Display groups
                    for group_idx in sorted(groups.keys()):
                        group_relations = groups[group_idx]

                        if len(groups) > 1:
                            st.write(f"**Group {group_idx + 1}** (AND with other groups):")

                        # Show images in this group
                        cols = st.columns(min(len(group_relations), 6))

                        for i, rel in enumerate(group_relations):
                            with cols[i % 6]:
                                if rel["image_chunk_id"]:
                                    # Get thumbnail via parent page
                                    thumb = get_image_chunk_thumbnail(rel["image_chunk_id"])
                                    if thumb:
                                        st.image(thumb, width=100)
                                    st.caption(f"IC: {rel['image_chunk_id'][:8]}...")

                        if len(groups) == 1 and len(group_relations) > 1:
                            st.caption("(OR: any of these is correct)")

                    if len(groups) > 1:
                        st.info("This is a multi-hop query (AND): all groups must be satisfied")
                else:
                    st.info("No retrieval ground truth")

with tab2:
    st.subheader("Dataset Statistics")

    service = get_service()

    try:
        stats = service.get_statistics()

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Files", stats.get("files", 0))
            st.metric("Documents", stats.get("documents", 0))
            st.metric("Pages", stats.get("pages", 0))

        with col2:
            image_chunks = stats.get("image_chunks", {})
            if isinstance(image_chunks, dict):
                st.metric("Image Chunks (Total)", image_chunks.get("total", 0))
                st.metric("Image Chunks (With Embedding)", image_chunks.get("with_embedding", 0))
            else:
                st.metric("Image Chunks", image_chunks)

            st.metric("Queries", stats.get("queries", 0))

        st.divider()

        # Query distribution
        st.subheader("Query Distribution")

        with service._create_uow() as uow:
            all_queries = uow.queries.get_all()

            # Count by relation type
            single_hop = 0
            multi_hop = 0
            or_queries = 0

            for query in all_queries:
                relations = uow.retrieval_relations.get_by_query_id(query.id)
                if relations:
                    group_indices = {r.group_index for r in relations}
                    if len(group_indices) > 1:
                        multi_hop += 1
                    elif len(relations) > 1:
                        or_queries += 1
                    else:
                        single_hop += 1

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Single-hop Queries", single_hop)
        with col2:
            st.metric("OR Queries", or_queries)
        with col3:
            st.metric("Multi-hop (AND) Queries", multi_hop)

    except Exception as e:
        st.error(f"Error loading statistics: {e}")

# Export section
st.divider()
st.subheader("Export Data")

col1, col2 = st.columns(2)

with col1:
    if st.button("Export Queries as JSON"):
        service = get_service()
        with service._create_uow() as uow:
            queries = uow.queries.get_all()

            export_data = []
            for query in queries:
                relations = uow.retrieval_relations.get_by_query_id(query.id)

                query_data = {
                    "id": query.id,
                    "contents": query.contents,
                    "query_to_llm": query.query_to_llm,
                    "generation_gt": query.generation_gt,
                    "retrieval_gt": [
                        {
                            "group_index": r.group_index,
                            "group_order": r.group_order,
                            "image_chunk_id": r.image_chunk_id,
                        }
                        for r in relations
                    ],
                }
                export_data.append(query_data)

        import json

        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download JSON",
            data=json_str,
            file_name="queries_export.json",
            mime="application/json",
        )

with col2:
    st.info(
        """
        **Export includes:**
        - Query ID, contents, query_to_llm
        - Generation ground truth
        - Retrieval ground truth (image chunk IDs with group info)
        """
    )
