from typing import Any

from pydantic import BaseModel, Field, computed_field

from src.shared.settings.app_settings import AnyRule


class DataTransformationReport(BaseModel):
    """A report summarizing the data transformation process.

    This model captures all results of a transformation run, including the transformed 
    dataset, mapping updates, and details on any errors or missing variables encountered.

    Attributes:
        enriched_variable_to_readable_mapping (dict[str, str]): Mapping from human-readable 
            column names to variable names after transformations.
        enriched_data (list[dict[str, Any]]): The final transformed data rows.
        applied_rules (list[AnyRule]): List of rules that were processed.
        missing_vars_required_by_rules (dict[str, list[AnyRule]]): Variables 
            found in rules but missing from the original mapping.
        var_name_conflicts (list[AnyRule]): Rules that failed due to existing variable names.
        field_reports_by_rule (dict[str, list[tuple[str, str]]]): Detailed field-level
            transformation history per rule.
        error_reports_by_rule (dict[str, list[tuple[str, str | None]]]): Error messages
            encountered during transformation per rule.
        fatal_errors (dict[str, str]): Fatal error messages encountered during transformation per rule.
    """

    enriched_variable_to_readable_mapping: dict[str, str] = Field(
        default_factory=dict, 
        description="A mapping from human-readable column names to variable names."
    )
    enriched_data: list[dict[str, Any]] = Field(
        default_factory=list, 
        description="The loaded and transformed data rows."
    )
    applied_rules: list[AnyRule] = Field(
        default_factory=list, 
        description="A list of transformation rules that were applied."
    )
    missing_vars_required_by_rules: dict[str, list[AnyRule]] = Field(
        default_factory=dict, 
        description="Variables required by rules but not present in the mapping."
    )
    var_name_conflicts: list[AnyRule] = Field(
        default_factory=list, 
        description="Rules that could not be applied due to variable name conflicts."
    )
    field_reports_by_rule: dict[str, list[tuple[str, str]]] = Field(
        default_factory=dict, 
        description="Mapping of rules to field-level transformation reports."
    )
    error_reports_by_rule: dict[str, list[tuple[str, str | None]]] = Field(
        default_factory=dict, 
        description="Mapping of rules to error reports generated during application."
    )
    fatal_errors: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of rules to fatal error messages encountered during application."
    )

    @computed_field
    @property
    def any_error_reports(self) -> bool:
        for error_list in self.error_reports_by_rule.values():
            if any(error_msg is not None for _, error_msg in error_list):
                return True
        return False
    
    @computed_field
    @property
    def any_fatal_errors(self) -> bool:
        return bool(self.fatal_errors)
    
    @computed_field
    @property
    def any_missing_vars(self) -> bool:
        return bool(self.missing_vars_required_by_rules)
    
    @computed_field
    @property
    def any_var_name_conflicts(self) -> bool:
        return bool(self.var_name_conflicts)

    @computed_field
    @property
    def any_errors(self) -> bool:
        """Indicates if any errors were encountered during the transformation process.

        Returns:
            bool: True if there are any errors or fatal errors, False otherwise.
        """
        any_error_reports = self.any_error_reports

        any_fatal_errors = self.any_fatal_errors

        any_missing_vars = self.any_missing_vars

        any_var_name_conflicts = self.any_var_name_conflicts

        any_errors = any_error_reports or any_fatal_errors or any_missing_vars or any_var_name_conflicts

        return any_errors
    
    