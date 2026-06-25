from __future__ import annotations

import io

import pandas as pd
import requests
import streamlit as st

from src.core.data_loading.data_loader_report import DataLoaderReport

ROW_NUMBER_OFFSET = 3
API_ENDPOINT = "http://localhost:8000/process-excel"


class ReconstructedFile(io.BytesIO):
    """A file-like object reconstructed from session state.

    Attributes:
        name (str): The name of the file.
        type (str): The MIME type of the file.
    """

    def __init__(self, content: bytes, name: str, file_type: str) -> None:
        """Initializes the ReconstructedFile.

        Args:
            content (bytes): The raw bytes of the file.
            name (str): The filename.
            file_type (str): The MIME type of the file.
        """
        super().__init__(content)
        self.name = name
        self.type = file_type


def get_active_file() -> io.BytesIO | None:
    """Determines the active file to use from the uploader or session state.

    Returns:
        The active file-like object or None if no file is available.
    """
    # TODO: Check for "xls" compatibility and handle accordingly
    uploaded_file = st.file_uploader("Upload Excel template file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # If the user uploaded a file, check if it's different from what's in session state
        if (
            "stored_file" in st.session_state
            and st.session_state.stored_file is not None
        ):
            if st.session_state.stored_file["name"] != uploaded_file.name:
                st.session_state.report = None
                st.session_state.stored_file = None
        return uploaded_file

    if ("stored_file" in st.session_state) and (st.session_state.stored_file is not None):
        # Reconstruct file-like object from session state
        stored = st.session_state.stored_file
        return ReconstructedFile(stored["bytes"], stored["name"], stored["type"])

    return None


def process_and_store_file(active_file: io.BytesIO) -> None:
    """Sends the file to the API and updates the session state.

    Args:
        active_file (io.BytesIO): The file to be processed.

    Raises:
        requests.RequestException: If the API request fails.
    """
    # Determine file type for the multipart/form-data request
    file_type = getattr(
        active_file,
        "type",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    files = {"file": (active_file.name, active_file.getvalue(), file_type)}

    with st.spinner("Processing template..."):
        response = requests.post(API_ENDPOINT, files=files)
        response.raise_for_status()

    # Store the report in session state to persist across reruns/navigation
    st.session_state.report = DataLoaderReport(**response.json())
    # ALSO store the file data in session state
    st.session_state.stored_file = {
        "name": active_file.name,
        "bytes": active_file.getvalue(),
        "type": file_type,
    }
    st.success(f"Successfully processed: **{st.session_state.report.filename}**")


def render_report_ui(report: DataLoaderReport) -> None:
    """Renders the data validation and mapping UI components.

    Args:
        report (DataLoaderReport): The report object containing loaded data and issues.
    """
    tab_data, tab_mapping, tab_errors = st.tabs(
        ["📊 Loaded Data", "🗺️ Variable Mapping", "⚠️ Validation Errors"]
    )

    # Tab 1: Render the Main DataFrame
    with tab_data:
        if report.loaded_data:
            df = pd.DataFrame(report.loaded_data)
            st.subheader("Parsed Sheet Preview")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No data rows loaded.")

    # Tab 2: Render Variable Mappings
    with tab_mapping:
        st.subheader("Readable Labels to Docx Variable Names")
        mapping_df = pd.DataFrame(
            [
                {"Friendly Label": k, "Docx Variable": v}
                for k, v in report.variable_to_readable_mapping.items()
            ]
        )
        st.dataframe(mapping_df, use_container_width=True, hide_index=True)

    # Tab 3: Render Validation Warnings & Errors
    with tab_errors:
        st.subheader("Data Validation Report")

        if not report.any_issues:
            st.success(
                "🎉 All checks passed! No missing fields or duplicate variables found."
            )
        else:
            if report.any_missing_readable_names:
                st.warning(
                    f"Missing Friendly Names in columns: {report.missing_readable_names} (These names were replaced with placeholders)"
                )

            if report.any_missing_variable_names:
                st.error(
                    f"Missing Docx Variable Names in columns: {report.missing_variable_names} (These columns were skipped)"
                )

            if report.any_duplicate_variable_names:
                st.error(
                    "Duplicate variables found (These will cause generation failures):"
                )
                for col_idx, var_name in report.duplicate_variable_names:
                    st.write(
                        f"- Column `{col_idx}` has a duplicated variable: `{var_name}`"
                    )

            if report.any_duplicate_readable_names:
                st.warning(
                    "Duplicate friendly names found (These will be replaced with placeholders):"
                )
                for col_idx, readable_name in report.duplicate_readable_names:
                    st.write(
                        f"- Column `{col_idx}` has a duplicated friendly name: `{readable_name}`"
                    )

            if report.any_missing_row_column_fields:
                st.warning("Found empty/missing data cells:")
                for row, col in report.missing_row_column_fields:
                    # Convert 0-indexed pandas to Excel's 1-indexed row number
                    # +3 because we skipped first 2 rows for headers
                    excel_row = row + ROW_NUMBER_OFFSET
                    st.write(
                        f"- Missing data cell at **Row {row} (Excel row {excel_row})**, Column index `{col}`"
                    )


def main() -> None:
    """Main entry point for the data loading page."""
    st.set_page_config(page_title="Load Data", page_icon="📥")
    st.title("📥 Load Data")
    active_file = get_active_file()

    if active_file is not None:
        if st.button("Upload file"):
            try:
                process_and_store_file(active_file)
            except Exception as e:
                st.error(f"Error parsing file: {e}")

        if ("report" in st.session_state) and (st.session_state.report is not None):
            render_report_ui(st.session_state.report)


if __name__ == "__main__":
    main()
