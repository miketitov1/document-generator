import logging
from pathlib import Path
from docxtpl import DocxTemplate
from jinja2 import Template, Environment, meta

from src.core.document_generation.document_generation_report import (
    DocumentGenerationReport,
    TemplateRenderingReport,
    TemplateFileInfo,
)
from src.core.exceptions.application_error import ApplicationError
from src.core.document_generation.word_page_counter import WordPageCounter
from src.core.utils.path_utils import init_dir, sanitize_path_component

LOGGER = logging.getLogger(__name__)

# Reusable Jinja2 environment for template parsing
JINJA_ENV = Environment()


# TODO: Refactor for async support in the future.
# TODO: Properly handle cases where there is no variables in the word template file name or in the path template for the subfolder name. Currently, if there are no variables in the template file name or the subfolder name, the code will still work but it produce files with the same name so they may overwrite each other. We can add a check to see if there are any variables in the template file name and the subfolder name, and if not, we can add a suffix to the rendered template name to make it unique. This will prevent overwriting of files and ensure that all generated documents are saved correctly.
def generate_document(
    data_row: dict[str, str],
    template_file_info: TemplateFileInfo,
    page_counter: WordPageCounter,
) -> TemplateRenderingReport:
    """
    Generates Word documents for a single data row based on the provided templates and updates the missing and used variables sets.

    Args:
        data_row (dict[str, str]): The enriched data for the current row.
        template_file_info (TemplateFileInfo): Information about the template file.
        page_counter (WordPageCounter): An instance of the WordPageCounter class to use for counting pages in the generated document.

    Returns:
        TemplateRenderingReport: A tuple containing info about the rendering process.
    """
    template_path = template_file_info.template_path
    templated_output_path = template_file_info.templated_output_path

    # Render and sanitize each path component separately to prevent data values
    # containing path separators (e.g., "72/6") from creating extra subdirectories.
    # Only process the relative parts (template structure), preserving the base output path.
    template_path_vars: set[str] = set()
    rendered_parts: list[str] = []

    relative_path = templated_output_path.relative_to(template_file_info.base_output_path)
    for part in relative_path.parts:
        # Extract variables from this part before rendering
        parsed_content = JINJA_ENV.parse(part)
        part_vars = meta.find_undeclared_variables(parsed_content)
        template_path_vars.update(part_vars)

        # Render this part as a Jinja2 template
        part_template = Template(part)
        rendered_part = part_template.render(**data_row)

        # Sanitize the rendered part to prevent path traversal
        sanitized_part = sanitize_path_component(rendered_part)
        rendered_parts.append(sanitized_part)

    rendered_output_path = template_file_info.base_output_path.joinpath(*rendered_parts)

    # Render document
    doc = DocxTemplate(template_path)
    doc.render(data_row)
    template_vars = doc.get_undeclared_template_variables()
    if not rendered_output_path.parent.exists():
        rendered_output_path.parent.mkdir(parents=True)
    doc.save(rendered_output_path)
    generated_page_count = page_counter.count_pages(rendered_output_path)

    return TemplateRenderingReport(
        initial_template_path=template_path,
        templated_output_path=templated_output_path,
        rendered_output_path=rendered_output_path,
        template_pages=template_file_info.page_count,
        rendered_pages=generated_page_count,
        templated_path_vars=template_path_vars,
        template_vars=template_vars,
        data_row=data_row,
    )


def process_data_row(
    data_row: dict[str, str],
    template_files_info: list[TemplateFileInfo],
    page_counter: WordPageCounter,
) -> list[TemplateRenderingReport]:
    """
    Processes a single data row to generate a Word document based on the templates and updates the generation report.

    Args:
        data_row (dict[str, str]): The enriched data for the current row.
        template_files_info (list[TemplateFileInfo]): A list of template file information.
        page_counter (WordPageCounter): An instance of the WordPageCounter class to use for counting pages in the generated document.

    Returns:
        list[TemplateRenderingReport]: A list of TemplateRenderingReport objects containing information about the rendering process for each template.
    """
    template_rendering_reports: list[TemplateRenderingReport] = []
    for template_file_info in template_files_info:
        try:
            report = generate_document(
                data_row,
                template_file_info,
                page_counter,
            )
            if report.page_overflow:
                LOGGER.warning(
                    "The generated document '%s' has %d page(s), which exceeds the original template page count of %d. This may indicate a page overflow issue.",
                    report.rendered_output_path,
                    report.rendered_pages,
                    report.template_pages,
                )
            if report.missing_templated_path_vars:
                LOGGER.warning(
                    "The following variables used in the template path for '%s' are missing from the data row: %s. The generated document may not be correct.",
                    template_file_info.template_path.name,
                    report.missing_templated_path_vars,
                )
            if report.missing_template_vars:
                LOGGER.warning(
                    "The following variables used in the template '%s' are missing from the data row: %s. The generated document may not be correct.",
                    template_file_info.template_path.name,
                    report.missing_template_vars,
                )
            if not report.used_template_vars:
                LOGGER.warning(
                    "None of the variables used in the template '%s' are present in the data row. The generated document may not be correct.",
                    template_file_info.template_path.name,
                )
            template_rendering_reports.append(report)

        except Exception as e:
            LOGGER.error(
                "Error while generating document for template '%s': %s",
                template_file_info.template_path.name,
                str(e),
            )
            report = TemplateRenderingReport(
                initial_template_path=template_file_info.template_path,
                templated_output_path=template_file_info.templated_output_path,
                data_row=data_row,
                template_pages=template_file_info.page_count,
                error_message=str(e),
            )
            template_rendering_reports.append(report)

    return template_rendering_reports


def generate_documents(
    enriched_data: list[dict[str, str]],
    templates_folder: Path,
    output_folder: Path,
) -> DocumentGenerationReport:
    """
    Generates documents based on the enriched data and returns a report of the generation results.

    Args:
        enriched_data (list[dict[str, str]]): The enriched data to use for document generation.
        templates_folder (Path): The folder containing the Word templates to use for generation.
        output_folder (Path): The folder where the generated Word documents should be saved.

    Returns:
        DocumentGenerationReport: A report of the generation results.
    """
    LOGGER.info("Starting document generation for %d data rows.", len(enriched_data))
    LOGGER.info("Templates folder: %s", templates_folder)
    LOGGER.info("Output folder: %s", output_folder)

    if not templates_folder.is_dir():
        raise ApplicationError(
            "Document Generation Error",
            f"Templates folder does not exist: {templates_folder}",
        )

    init_dir(output_folder)

    # Convert all values to strings for template compatibility.
    # DataTransformationReport.enriched_data uses dict[str, Any] which can contain
    # int/float values from Excel, but TemplateRenderingReport expects dict[str, str].
    str_data: list[dict[str, str]] = [
        {k: str(v) if v is not None else "" for k, v in row.items()}
        for row in enriched_data
    ]

    # ! The generator will respect each template files relative path to the templates folder
    # ! So if there is a subfolder in the templates folder, it will be preserved in the output folder
    template_files = list(templates_folder.rglob("*.docx"))
    if template_files:
        LOGGER.info(
            "Found %d template(s) in the templates folder.", len(template_files)
        )
    else:
        LOGGER.error(
            "No Word templates found in the templates folder: %s",
            templates_folder,
        )
        return DocumentGenerationReport(
            enriched_data=str_data,
            templates_folder=templates_folder,
            output_folder=output_folder,
            any_templates_provided=False,
        )

    page_counter = WordPageCounter()
    template_files_info: list[TemplateFileInfo] = []
    for template_path in template_files:
        templated_output_path = output_folder / template_path.relative_to(
            templates_folder
        )
        page_count = page_counter.count_pages(template_path)
        template_files_info.append(
            TemplateFileInfo(
                template_path=template_path,
                base_output_path=output_folder,
                templated_output_path=templated_output_path,
                page_count=page_count,
            )
        )
        LOGGER.info("Template '%s' has %d page(s).", template_path.name, page_count)

    template_rendering_reports: list[list[TemplateRenderingReport]] = []
    for data_row in str_data:
        generation_report = process_data_row(
            data_row,
            template_files_info,
            page_counter,
        )
        template_rendering_reports.append(generation_report)

    return DocumentGenerationReport(
        enriched_data=str_data,
        templates_folder=templates_folder,
        output_folder=output_folder,
        any_templates_provided=True,
        template_files_info=template_files_info,
        template_rendering_reports=template_rendering_reports,
    )
