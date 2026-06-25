from typing import Any

from pydantic import BaseModel, Field, computed_field


class DataLoaderReport(BaseModel):
    """A report summarizing the data loading process.

    This class holds metadata and error logs regarding the ingestion of
    source files, including mapping accuracy and missing field detection.
    """

    filename: str = Field(
        default="unknown.xlsx",
        description="The name of the source file that was processed.",
    )
    variable_to_readable_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="A mapping from human-readable column names to variable names.",
    )
    loaded_data: list[dict[str, Any]] = Field(
        default_factory=list, description="The loaded data rows."
    )

    missing_readable_names: list[int] = Field(
        default_factory=list,
        description="List of indices for columns with missing readable names.",
    )
    missing_variable_names: list[int] = Field(
        default_factory=list,
        description="List of indices for columns with missing variable names.",
    )

    duplicate_readable_names: list[tuple[int, str]] = Field(
        default_factory=list,
        description="List of indices and names for columns with duplicate readable names.",
    )
    duplicate_variable_names: list[tuple[int, str]] = Field(
        default_factory=list,
        description="List of indices and names for columns with duplicate variable names.",
    )

    missing_row_column_fields: list[tuple[int, int]] = Field(
        default_factory=list,
        description="List of (row, column) indices for missing fields.",
    )

    @computed_field
    @property
    def any_missing_readable_names(self) -> bool:
        return bool(self.missing_readable_names)
    
    @computed_field
    @property
    def any_missing_variable_names(self) -> bool:
        return bool(self.missing_variable_names)
    
    @computed_field
    @property
    def any_duplicate_readable_names(self) -> bool:
        return bool(self.duplicate_readable_names)
    
    @computed_field
    @property
    def any_duplicate_variable_names(self) -> bool:
        return bool(self.duplicate_variable_names)
    
    @computed_field
    @property
    def any_missing_row_column_fields(self) -> bool:
        return bool(self.missing_row_column_fields)
    
    @computed_field
    @property
    def any_issues(self) -> bool:
        return (
            self.any_missing_readable_names
            or self.any_missing_variable_names
            or self.any_duplicate_readable_names
            or self.any_duplicate_variable_names
            or self.any_missing_row_column_fields
        )
