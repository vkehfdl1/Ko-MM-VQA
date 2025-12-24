"""Query input form component."""

from dataclasses import dataclass

import streamlit as st


@dataclass
class QueryFormData:
    """Data from query form submission."""

    query_text: str
    query_to_llm: str | None
    generation_gt: list[str]
    relation_type: str  # "or" or "and"

    def is_valid(self) -> tuple[bool, list[str]]:
        """Validate form data.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not self.query_text or not self.query_text.strip():
            errors.append("Query text is required")

        if len(self.query_text) > 2000:
            errors.append("Query text must be less than 2000 characters")

        if self.relation_type not in ("or", "and"):
            errors.append("Invalid relation type")

        # Generation GT is required
        if not self.generation_gt or len(self.generation_gt) == 0:
            errors.append("At least one Generation Ground Truth is required")

        # Check for empty generation_gt entries
        empty_entries = [i for i, gt in enumerate(self.generation_gt) if not gt.strip()]
        if empty_entries:
            errors.append(f"Generation GT entries cannot be empty (check entry {empty_entries[0] + 1})")

        return len(errors) == 0, errors


def query_input_form(
    key_prefix: str = "query_form",
    show_relation_type: bool = True,
) -> QueryFormData | None:
    """Render query input form with dynamic generation GT list.

    Args:
        key_prefix: Unique prefix for widget keys
        show_relation_type: Whether to show relation type selector

    Returns:
        QueryFormData if form is submitted and valid, None otherwise
    """
    # Initialize session state for generation_gt list
    gt_key = f"{key_prefix}_generation_gt_list"
    if gt_key not in st.session_state:
        st.session_state[gt_key] = [""]  # Start with one empty entry

    generation_gt_list: list[str] = st.session_state[gt_key]

    st.subheader("Query Information")

    # Query text (required)
    query_text = st.text_area(
        "Query *",
        placeholder="Enter the question that requires the selected pages to answer...",
        help="The main query text that will be used for retrieval evaluation",
        key=f"{key_prefix}_query_text",
    )

    # Query to LLM (optional)
    query_to_llm = st.text_area(
        "Query to LLM (optional)",
        placeholder="Alternative query text to send to LLM (if different from main query)",
        help="If provided, this will be sent to the LLM instead of the main query",
        key=f"{key_prefix}_query_to_llm",
    )

    # Generation ground truth (required, dynamic list)
    st.divider()
    st.write("**Generation Ground Truth (required)** *")
    st.caption("Add expected answers. Each entry can contain multiple lines.")

    # Render each generation GT entry
    updated_list = []
    items_to_remove = []

    for i, gt_value in enumerate(generation_gt_list):
        col1, col2 = st.columns([6, 1])
        with col1:
            new_value = st.text_area(
                f"Answer {i + 1}",
                value=gt_value,
                placeholder=f"Enter answer {i + 1}...",
                key=f"{key_prefix}_gt_{i}",
                height=100,
                label_visibility="collapsed",
            )
            updated_list.append(new_value)
        with col2:
            st.write("")  # Spacer
            if len(generation_gt_list) > 1 and st.button(
                "🗑️", key=f"{key_prefix}_remove_gt_{i}", help="Remove this answer"
            ):
                items_to_remove.append(i)

    # Handle removals
    if items_to_remove:
        for idx in sorted(items_to_remove, reverse=True):
            updated_list.pop(idx)
        st.session_state[gt_key] = updated_list
        st.rerun()

    # Add button
    if st.button("Add Answer", key=f"{key_prefix}_add_gt"):
        updated_list.append("")
        st.session_state[gt_key] = updated_list
        st.rerun()

    # Update session state with current values
    st.session_state[gt_key] = updated_list

    # Relation type
    if show_relation_type:
        st.divider()
        st.write("**Relation Type:**")

        col1, col2 = st.columns(2)
        with col1:
            relation_type = st.radio(
                "Select type",
                options=["and", "or"],
                format_func=lambda x: (
                    "AND (all pages required - multi-hop)" if x == "and" else "OR (any page is correct)"
                ),
                key=f"{key_prefix}_relation_type",
                horizontal=True,
            )

        with col2:
            if relation_type == "or":
                st.info("**OR**: Any of the selected pages contains the answer.")
            else:
                st.info("**AND**: All selected pages are required together (multi-hop reasoning).")
    else:
        relation_type = "and"

    st.divider()

    # Submit button
    if st.button("Submit Query", type="primary", key=f"{key_prefix}_submit"):
        # Filter out empty entries for final submission
        generation_gt = [gt for gt in updated_list if gt.strip()]

        form_data = QueryFormData(
            query_text=query_text.strip() if query_text else "",
            query_to_llm=query_to_llm.strip() if query_to_llm and query_to_llm.strip() else None,
            generation_gt=generation_gt,
            relation_type=relation_type,
        )

        return form_data

    return None


def clear_query_form(key_prefix: str = "query_form") -> None:
    """Clear query form state.

    Args:
        key_prefix: The key prefix used in query_input_form
    """
    gt_key = f"{key_prefix}_generation_gt_list"
    if gt_key in st.session_state:
        st.session_state[gt_key] = [""]


def render_query_preview(form_data: QueryFormData, page_count: int) -> None:
    """Render preview of query data before submission.

    Args:
        form_data: Query form data
        page_count: Number of selected pages
    """
    st.subheader("Preview")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Query:**")
        st.write(form_data.query_text[:200] + "..." if len(form_data.query_text) > 200 else form_data.query_text)

        if form_data.query_to_llm:
            st.write("**객관식 쿼리:**")
            st.write(
                form_data.query_to_llm[:100] + "..." if len(form_data.query_to_llm) > 100 else form_data.query_to_llm
            )

    with col2:
        st.write("**Generation GT:**")
        if form_data.generation_gt:
            for i, gt in enumerate(form_data.generation_gt[:3]):
                # Show first line of each GT
                first_line = gt.split("\n")[0]
                display = first_line[:50] + "..." if len(first_line) > 50 else first_line
                if "\n" in gt:
                    display += " (multiline)"
                st.write(f"{i + 1}. {display}")
            if len(form_data.generation_gt) > 3:
                st.write(f"  ... and {len(form_data.generation_gt) - 3} more")
        else:
            st.write("(none)")

        st.write("**Relation:**")
        if form_data.relation_type == "or":
            st.write(f"OR - any of {page_count} pages")
        else:
            st.write(f"AND - all {page_count} pages required")
