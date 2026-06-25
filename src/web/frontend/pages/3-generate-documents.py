from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.core.data_transformation.data_transformation_report import (
    DataTransformationReport,
)
from src.core.document_generation.document_generation_report import (
    DocumentGenerationReport,
    TemplateFileInfo,
)

GENERATE_ENDPOINT = "http://localhost:8000/generate-documents"
GENERATE_REPORT_STATE_KEY = "generate_report"
GENERATE_DOWNLOAD_URL_STATE_KEY = "generate_download_url"
GENERATE_SOURCE_FILENAME_STATE_KEY = "generate_source_filename"
GENERATE_ZIP_STATE_KEY = "generate_zip"


# ─── Session state helpers ────────────────────────────────────────────────


class ReconstructedFile(io.BytesIO):
    """A file-like object reconstructed from session state.

    Attributes:
        name (str): The name of the file.
        type (str): The MIME type of the file.
    """

    def __init__(self, content: bytes, name: str, file_type: str) -> None:
        """Initialize the reconstructed file.

        Args:
            content (bytes): The raw bytes of the file.
            name (str): The filename.
            file_type (str): The MIME type of the file.
        """
        super().__init__(content)
        self.name = name
        self.type = file_type


def get_transform_report() -> DataTransformationReport | None:
    """Reads the transformed-data report from session state.

    Returns:
        DataTransformationReport | None: The report if present and valid.
    """
    report = st.session_state.get("transform_report")
    if isinstance(report, DataTransformationReport):
        return report
    return None


def invalidate_stale_generate_report(
    transform_report: DataTransformationReport | None,
) -> None:
    """Clears stale generate results when the source data changed.

    Args:
        transform_report (DataTransformationReport | None): The current transform report.
    """
    stored_filename = st.session_state.get(GENERATE_SOURCE_FILENAME_STATE_KEY)

    # If the source transform report changed, invalidate stored generation results
    if transform_report is None:
        _clear_generate_state()
        return

    current_filename = getattr(
        st.session_state.get("report"), "filename", None
    )
    if stored_filename != current_filename:
        _clear_generate_state()


def _clear_generate_state() -> None:
    """Removes all generate-related keys from session state."""
    st.session_state.pop(GENERATE_REPORT_STATE_KEY, None)
    st.session_state.pop(GENERATE_DOWNLOAD_URL_STATE_KEY, None)
    st.session_state.pop(GENERATE_SOURCE_FILENAME_STATE_KEY, None)
    st.session_state.pop(GENERATE_ZIP_STATE_KEY, None)


# ─── Template zip uploader ────────────────────────────────────────────────


def get_template_zip_file() -> io.BytesIO | None:
    """Determines the active zip file from the uploader or session state.

    Returns:
        The active file-like object or None if no file is available.
    """
    uploaded_file = st.file_uploader(
        "Upload ZIP archive with .docx templates",
        type=["zip"],
        key="template_zip_uploader",
    )

    if uploaded_file is not None:
        stored_zip = st.session_state.get(GENERATE_ZIP_STATE_KEY)
        if stored_zip is not None and stored_zip["name"] != uploaded_file.name:
            _clear_generate_state()
        return uploaded_file

    stored_zip = st.session_state.get(GENERATE_ZIP_STATE_KEY)
    if stored_zip is not None:
        return ReconstructedFile(
            stored_zip["bytes"], stored_zip["name"], stored_zip["type"]
        )

    return None


def store_template_zip(active_file: io.BytesIO) -> None:
    """Stores the template zip file in session state.

    Args:
        active_file (io.BytesIO): The zip file to store.
    """
    file_type = getattr(active_file, "type", "application/zip")
    st.session_state[GENERATE_ZIP_STATE_KEY] = {
        "name": active_file.name,
        "bytes": active_file.getvalue(),
        "type": file_type,
    }


# ─── API communication ────────────────────────────────────────────────────


def _extract_error_detail(response: requests.Response) -> str:
    """Extract a human-readable error detail from an HTTP response.

    Attempts to parse the response body as JSON (typical for FastAPI 422
    validation errors) and returns a formatted string. Falls back to the
    raw response text if JSON parsing fails.

    Args:
        response (requests.Response): The failed HTTP response.

    Returns:
        str: A detailed error message from the response body.
    """
    try:
        error_json = response.json()
    except (ValueError, KeyError):
        return response.text or "No error details available"

    # FastAPI 422 responses include a "detail" key with a list of validation errors
    if "detail" in error_json:
        detail = error_json["detail"]
        if isinstance(detail, list):
            parts: list[str] = []
            for err in detail:
                loc = " -> ".join(str(v) for v in err.get("loc", []))
                msg = err.get("msg", "")
                parts.append(f"{msg}" + (f" (field: {loc})" if loc else ""))
            return "; ".join(parts)
        return str(detail)

    return str(error_json)


def call_generate_api(
    transform_report: DataTransformationReport,
    template_zip: io.BytesIO,
) -> tuple[DocumentGenerationReport, str]:
    """Sends transformed data and templates to the backend for document generation.

    The report is serialized to JSON and sent as a form field to avoid
    FastAPI's inability to parse complex Pydantic models from multipart
    form data (which occurs when both a body model and file upload are used).

    Args:
        transform_report (DataTransformationReport): The transformed data report.
        template_zip (io.BytesIO): The zip file containing template documents.

    Returns:
        tuple[DocumentGenerationReport, str]: The generation report and the
            download URL for the generated ZIP archive.

    Raises:
        requests.HTTPError: If the API request fails, with response attached
            so the caller can extract error details.
    """
    file_type = getattr(template_zip, "type", "application/zip")
    files = {"template_files_zipped": (template_zip.name, template_zip.getvalue(), file_type)}

    # Serialize the report to JSON and send as a form field
    form_data = {
        "content": transform_report.model_dump_json(),
    }

    response = requests.post(
        GENERATE_ENDPOINT,
        data=form_data,
        files=files,
        timeout=300,
    )
    response.raise_for_status()
    api_response = response.json()

    report = DocumentGenerationReport.model_validate(api_response["report"])
    download_url = api_response["download_url"]
    return report, download_url


def download_generated_archive(download_url: str) -> bytes:
    """Downloads the generated documents archive from the backend.

    Args:
        download_url (str): The URL to download the archive from.

    Returns:
        bytes: The zip archive content.

    Raises:
        requests.RequestException: If the download request fails.
    """
    full_url = f"http://localhost:8000{download_url}" if download_url.startswith("/") else download_url
    response = requests.get(full_url, timeout=120)
    response.raise_for_status()
    return response.content


# ─── UI rendering helpers ─────────────────────────────────────────────────


def render_generation_status_tab(report: DocumentGenerationReport) -> None:
    """Renders Tab 1: a status table showing generation results per row and template.

    Each row corresponds to a data row, each column to a template.
    Green (✅) indicates success, red (❌) indicates an error.

    Args:
        report (DocumentGenerationReport): The document generation report.
    """
    st.subheader("Generation Status per Data Row and Template")

    if not report.any_templates_provided:
        st.info("No templates were provided for document generation.")
        return

    if not report.template_rendering_reports:
        st.info("No generation results available.")
        return

    template_names = [
        _template_file_short_path(info)
        for info in report.template_files_info
    ]

    status_rows: list[dict[str, str]] = []
    for row_idx, row_reports in enumerate(report.template_rendering_reports, start=1):
        status_row: dict[str, str] = {"Data Row": f"Row {row_idx}"}
        for template_idx, template_name in enumerate(template_names):
            if template_idx < len(row_reports):
                cell_report = row_reports[template_idx]
                status_row[template_name] = "✅" if not cell_report.has_error else "❌"
            else:
                status_row[template_name] = "❌"
        status_rows.append(status_row)

    status_df = pd.DataFrame(status_rows)
    st.dataframe(status_df, use_container_width=True, hide_index=True)


def _template_file_short_path(template_file_info: TemplateFileInfo) -> str:
    """Extracts a human-friendly short path for a template file.

    Args:
        template_file_info (TemplateFileInfo): A TemplateFileInfo instance.

    Returns:
        str: A shortened relative path string for display.
    """
    rel = template_file_info.template_path.relative_to(template_file_info.template_path.parent)
    return str(rel)


def render_errors_tab(report: DocumentGenerationReport) -> None:
    """Renders Tab 2: a comprehensive error report from generation results.

    Shows errors similar to how the load-data and transform-data pages
    report issues, using all available information from TemplateRenderingReport.

    Args:
        report (DocumentGenerationReport): The document generation report.
    """
    st.subheader("Document Generation Errors")

    if not report.template_rendering_reports:
        st.info("No generation results to report on.")
        return

    has_any_issue = False
    all_errors: list[dict[str, str]] = []

    for row_idx, row_reports in enumerate(report.template_rendering_reports, start=1):
        for template_idx, cell_report in enumerate(row_reports):
            template_name = _template_file_short_path(
                report.template_files_info[template_idx]
            ) if template_idx < len(report.template_files_info) else f"Template {template_idx}"

            # Direct generation errors
            if cell_report.has_error:
                all_errors.append({
                    "Data Row": f"Row {row_idx}",
                    "Template": template_name,
                    "Issue": "Generation Error",
                    "Detail": cell_report.error_message or "Unknown error",
                })
                has_any_issue = True

            # Missing templated path variables
            for var in cell_report.missing_templated_path_vars:
                all_errors.append({
                    "Data Row": f"Row {row_idx}",
                    "Template": template_name,
                    "Issue": "Missing Path Variable",
                    "Detail": f"Variable `{{{var}}}` in output path is missing from data",
                })
                has_any_issue = True

            # Missing template variables
            for var in cell_report.missing_template_vars:
                all_errors.append({
                    "Data Row": f"Row {row_idx}",
                    "Template": template_name,
                    "Issue": "Missing Template Variable",
                    "Detail": f"Variable `{{{var}}}` in template is missing from data",
                })
                has_any_issue = True

            # Page overflow warnings
            if cell_report.page_overflow:
                all_errors.append({
                    "Data Row": f"Row {row_idx}",
                    "Template": template_name,
                    "Issue": "Page Overflow",
                    "Detail": f"Generated document has {cell_report.rendered_pages} page(s), exceeding template pages ({cell_report.template_pages})",
                })
                has_any_issue = True

            # No template variables used warning
            if not cell_report.used_template_vars and not cell_report.has_error:
                all_errors.append({
                    "Data Row": f"Row {row_idx}",
                    "Template": template_name,
                    "Issue": "No Variables Used",
                    "Detail": "None of the template variables matched data row fields",
                })
                has_any_issue = True

    if not has_any_issue:
        st.success("🎉 All documents generated successfully with no issues detected!")
    else:
        errors_df = pd.DataFrame(all_errors)
        st.dataframe(errors_df, use_container_width=True, hide_index=True)


# ─── Main page entry point ────────────────────────────────────────────────


def main() -> None:
    """Main entry point for the generate-documents page."""
    st.set_page_config(page_title="Generate Documents", page_icon="📄")
    st.title("📄 Generate Documents")

    transform_report = get_transform_report()
    invalidate_stale_generate_report(transform_report)

    if transform_report is None:
        st.info(
            "Load and transform data on the previous pages first. "
            "Transformed data is required to generate documents."
        )
        return

    template_zip = get_template_zip_file()

    if st.button("Generate Documents", type="primary"):
        if template_zip is None:
            st.error("Please upload a ZIP archive containing .docx templates.")
            return

        # Store the zip in session state for persistence
        store_template_zip(template_zip)

        try:
            with st.spinner("Generating documents..."):
                generation_report, download_url = call_generate_api(
                    transform_report, template_zip
                )

            # Store in session state
            source_filename = getattr(
                st.session_state.get("report"), "filename", "unknown"
            )
            st.session_state[GENERATE_REPORT_STATE_KEY] = generation_report
            st.session_state[GENERATE_DOWNLOAD_URL_STATE_KEY] = download_url
            st.session_state[GENERATE_SOURCE_FILENAME_STATE_KEY] = source_filename

            st.success("Documents generated successfully!")

        except requests.HTTPError as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                detail = _extract_error_detail(response)
                st.error(f"Failed to generate documents (HTTP {response.status_code}): {detail}")
            else:
                st.error(f"Failed to generate documents: {exc}")
        except requests.RequestException as exc:
            st.error(f"Failed to generate documents: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error during document generation: {exc}")

    # Show results if a report exists in session state
    generate_report = st.session_state.get(GENERATE_REPORT_STATE_KEY)
    if isinstance(generate_report, DocumentGenerationReport):
        st.divider()

        download_url = st.session_state.get(GENERATE_DOWNLOAD_URL_STATE_KEY)
        if download_url:
            try:
                archive_bytes = download_generated_archive(download_url)
                archive_name = Path(download_url).name

                st.download_button(
                    label="📥 Download Generated Documents (ZIP)",
                    data=archive_bytes,
                    file_name=archive_name,
                    mime="application/zip",
                    type="primary",
                )
            except requests.RequestException as exc:
                st.error(f"Failed to prepare download: {exc}")

        tab_status, tab_errors = st.tabs(
            ["📋 Generation Status", "⚠️ Errors"]
        )

        with tab_status:
            render_generation_status_tab(generate_report)

        with tab_errors:
            render_errors_tab(generate_report)


if __name__ == "__main__":
    main()