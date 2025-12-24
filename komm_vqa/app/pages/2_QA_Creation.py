"""QA Creation page - Create queries with retrieval ground truth."""

import streamlit as st
from autorag_research.orm.models.retrieval_gt import and_all, image, or_all

from komm_vqa.app.components.page_selector import (
    clear_page_selection,
    page_number_selector,
    render_selected_pages_preview,
)
from komm_vqa.app.components.query_form import query_input_form, render_query_preview
from komm_vqa.app.config import render_settings_sidebar
from komm_vqa.app.db import check_db_connection, get_service

st.set_page_config(page_title="QA Creation", page_icon="❓", layout="wide")
st.title("❓ QA Creation")

# Render settings sidebar
render_settings_sidebar()

# Check connection
is_connected, message = check_db_connection()
if not is_connected:
    st.error(f"Database not connected: {message}")
    st.stop()


def create_query_with_retrieval_gt(
    query_text: str,
    query_to_llm: str | None,
    generation_gt: list[str] | None,
    image_chunk_ids: list[str],
    relation_type: str,
) -> str:
    """Create a query with retrieval ground truth.

    Args:
        query_text: Query contents
        query_to_llm: Optional alternative query for LLM
        generation_gt: List of ground truth answers
        image_chunk_ids: List of ImageChunk IDs
        relation_type: "or" or "and"

    Returns:
        Created query ID
    """
    service = get_service()

    # Create Query
    query_data = {
        "contents": query_text,
    }
    if query_to_llm:
        query_data["query_to_llm"] = query_to_llm
    if generation_gt:
        query_data["generation_gt"] = generation_gt

    query_ids = service.add_queries([query_data])
    query_id = query_ids[0]

    # Create Retrieval GT
    if len(image_chunk_ids) == 1:
        # Single image chunk
        gt = image(image_chunk_ids[0])
    elif relation_type == "or":
        gt = or_all(image_chunk_ids, image)
    else:  # "and"
        gt = and_all(image_chunk_ids, image)

    service.add_retrieval_gt(query_id, gt, chunk_type="image")

    return query_id


# Main content
st.write(
    """
    Create queries by selecting relevant pages and entering question/answer pairs.
    Each query links to one or more pages (image chunks) as retrieval ground truth.
    """
)

# Two-column layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Select Pages")
    selected_page_ids, selected_image_chunk_ids = page_number_selector(key_prefix="qa_creation")

with col2:
    st.subheader("2. Enter Query")

    if not selected_image_chunk_ids:
        st.warning("Please select at least one page from the left panel.")
    else:
        # Show selected pages preview
        st.write("**Selected pages:**")
        render_selected_pages_preview(selected_page_ids, columns=4)

        st.divider()

        # Query form
        form_data = query_input_form(key_prefix="qa_creation", show_relation_type=True)

        if form_data:
            # Validate
            is_valid, errors = form_data.is_valid()

            if not is_valid:
                for error in errors:
                    st.error(error)
            else:
                # Show preview
                render_query_preview(form_data, len(selected_page_ids))

                st.divider()

                # Confirm and create
                if st.button("Confirm and Create Query", type="primary"):
                    try:
                        query_id = create_query_with_retrieval_gt(
                            query_text=form_data.query_text,
                            query_to_llm=form_data.query_to_llm,
                            generation_gt=form_data.generation_gt if form_data.generation_gt else None,
                            image_chunk_ids=selected_image_chunk_ids,
                            relation_type=form_data.relation_type,
                        )

                        st.success(f"Query created successfully! ID: {query_id[:8]}...")

                        # Clear selections
                        clear_page_selection("qa_creation")
                        st.cache_data.clear()

                        # Ask if user wants to create another
                        if st.button("Create Another Query"):
                            st.rerun()

                    except Exception as e:
                        st.error(f"Error creating query: {e}")

# Show recent queries at the bottom
st.divider()
st.subheader("Recent Queries")

service = get_service()
with service._create_uow() as uow:
    # Get recent queries (latest 5)
    queries = uow.queries.get_all(limit=5)
    # Extract data while session is active to avoid DetachedInstanceError
    query_list = []
    for q in queries:
        relations = uow.retrieval_relations.get_by_query_id(q.id)
        group_indices = {r.group_index for r in relations}
        if len(group_indices) > 1:
            relation_type = "AND (multi-hop)"
        elif len(relations) > 1:
            relation_type = "OR"
        elif len(relations) == 1:
            relation_type = "Single"
        else:
            relation_type = None

        query_list.append({
            "id": q.id,
            "contents": q.contents,
            "query_to_llm": q.query_to_llm,
            "generation_gt": q.generation_gt,
            "relation_count": len(relations),
            "relation_type": relation_type,
        })

if query_list:
    for query_info in query_list:
        contents = query_info["contents"]
        with st.expander(f"Q: {contents[:50]}..." if len(contents) > 50 else f"Q: {contents}"):
            st.write(f"**ID:** {query_info['id']}")
            st.write(f"**Query:** {query_info['contents']}")
            if query_info["query_to_llm"]:
                st.write(f"**Query to LLM:** {query_info['query_to_llm']}")
            if query_info["generation_gt"]:
                st.write(f"**Generation GT:** {', '.join(query_info['generation_gt'][:3])}")

            if query_info["relation_count"] > 0:
                st.write(f"**Retrieval GT:** {query_info['relation_count']} image chunk(s)")
                st.write(f"**Type:** {query_info['relation_type']}")
else:
    st.info("No queries created yet.")
