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

        return len(errors) == 0, errors


def query_input_form(
    key_prefix: str = "query_form",
    show_relation_type: bool = True,
) -> QueryFormData | None:
    """Render query input form.

    Args:
        key_prefix: Unique prefix for widget keys
        show_relation_type: Whether to show relation type selector

    Returns:
        QueryFormData if form is submitted, None otherwise
    """
    with st.form(key=f"{key_prefix}_form"):
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

        # Generation ground truth (optional, multiple lines)
        generation_gt_text = st.text_area(
            "Generation Ground Truth (optional)",
            placeholder="Enter correct answers, one per line...\nAnswer 1\nAnswer 2",
            help="Expected answers for generation evaluation. Enter one answer per line.",
            key=f"{key_prefix}_generation_gt",
        )

        # Relation type
        if show_relation_type:
            st.divider()
            st.write("**Relation Type:**")

            col1, col2 = st.columns(2)
            with col1:
                relation_type = st.radio(
                    "Select type",
                    options=["or", "and"],
                    format_func=lambda x: (
                        "OR (any page is correct)" if x == "or" else "AND (all pages required - multi-hop)"
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
            relation_type = "or"

        # Submit button
        submitted = st.form_submit_button("Submit Query", type="primary")

        if submitted:
            # Parse generation_gt (one per line, filter empty)
            generation_gt = (
                [line.strip() for line in generation_gt_text.strip().split("\n") if line.strip()]
                if generation_gt_text
                else []
            )

            form_data = QueryFormData(
                query_text=query_text.strip(),
                query_to_llm=query_to_llm.strip() if query_to_llm and query_to_llm.strip() else None,
                generation_gt=generation_gt,
                relation_type=relation_type,
            )

            return form_data

    return None


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
            st.write("**Query to LLM:**")
            st.write(
                form_data.query_to_llm[:100] + "..." if len(form_data.query_to_llm) > 100 else form_data.query_to_llm
            )

    with col2:
        st.write("**Generation GT:**")
        if form_data.generation_gt:
            for gt in form_data.generation_gt[:3]:
                st.write(f"- {gt[:50]}..." if len(gt) > 50 else f"- {gt}")
            if len(form_data.generation_gt) > 3:
                st.write(f"  ... and {len(form_data.generation_gt) - 3} more")
        else:
            st.write("(none)")

        st.write("**Relation:**")
        if form_data.relation_type == "or":
            st.write(f"OR - any of {page_count} pages")
        else:
            st.write(f"AND - all {page_count} pages required")
