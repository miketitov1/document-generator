from pathlib import Path

from pydantic import BaseModel, Field, computed_field


class TemplateFileInfo(BaseModel):
    """
    Represents information about a template file, including its path and page count.
    """

    template_path: Path = Field(..., description="The path to the template file.")
    base_output_path: Path = Field(
        ..., description="The base output path for the generated document."
    )
    templated_output_path: Path = Field(
        ..., description="The path to the output file after templating."
    )
    page_count: int = Field(
        ..., description="The number of pages in the template file."
    )
    


class TemplateRenderingReport(BaseModel):
    """
    Represents a report of the document generation process for a single data row.
    """

    initial_template_path: Path = Field(
        ..., description="The initial template path before any rendering."
    )
    templated_output_path: Path = Field(..., description="The unrendered output path")
    data_row: dict[str, str] = Field(
        ..., description="The data row used for rendering the template."
    )
    template_pages: int = Field(
        ...,
        description="The number of pages in the template used for document generation.",
    )

    rendered_output_path: Path | None = Field(
        default=None,
        description="The final rendered path after applying the template and data row.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if any error occurred during the rendering process.",
    )

    templated_path_vars: set[str] = Field(
        default_factory=set,
        description="The set of all variables present in the templated output path.",
    )
    template_vars: set[str] = Field(
        default_factory=set,
        description="The set of all variables present in the template.",
    )

    rendered_pages: int | None = Field(
        default=None, description="The number of pages in the generated document."
    )

    @computed_field
    @property
    def has_error(self) -> bool:
        return self.error_message is not None

    @computed_field
    @property
    def page_overflow(self) -> bool:
        if self.rendered_pages is None:
            return False
        return self.rendered_pages > self.template_pages

    @computed_field
    @property
    def initial_vars(self) -> set[str]:
        return set(self.data_row.keys())

    @computed_field
    @property
    def missing_templated_path_vars(self) -> set[str]:
        return self.templated_path_vars - self.initial_vars

    @computed_field
    @property
    def unused_templated_path_vars(self) -> set[str]:
        return self.initial_vars - self.templated_path_vars

    @computed_field
    @property
    def used_templated_path_vars(self) -> set[str]:
        return self.templated_path_vars & self.initial_vars

    @computed_field
    @property
    def missing_template_vars(self) -> set[str]:
        return self.template_vars - self.initial_vars

    @computed_field
    @property
    def unused_template_vars(self) -> set[str]:
        return self.initial_vars - self.template_vars

    @computed_field
    @property
    def used_template_vars(self) -> set[str]:
        return self.template_vars & self.initial_vars


class DocumentGenerationReport(BaseModel):
    """
    Represents a report of the document generation process.
    """

    enriched_data: list[dict[str, str]] = Field(
        ...,
        description="A list of enriched data rows used for document generation.",
    )
    templates_folder: Path = Field(
        ...,
        description="The folder containing the templates used for document generation.",
    )
    output_folder: Path = Field(
        ..., description="The folder where the generated documents are saved."
    )
    any_templates_provided: bool = Field(
        ...,
        description="Indicates whether any templates were provided for document generation. Not derivable from template_page_counts because template_files are obtained before page count evaluation.",
    )
    template_files_info: list[TemplateFileInfo] = Field(
        default_factory=list,
        description="A list of TemplateFileInfo objects containing information about each template file used for document generation.",
    )
    template_rendering_reports: list[list[TemplateRenderingReport]] = Field(
        default_factory=list,
        description="A list of TemplateRenderingReport objects containing information about each document generation process. If a fatal error occurred during the generation process, the corresponding entry will be None.",
    )
