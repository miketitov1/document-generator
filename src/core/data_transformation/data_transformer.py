import json
import logging
import copy
from typing import NamedTuple, Any

from src.core.data_transformation.transformation_rule import TransformationRule
from src.core.data_transformation.data_transformation_report import (
    DataTransformationReport,
)
from src.shared.settings.app_settings import AnyRule

LOGGER = logging.getLogger(__name__)


def _build_rule_report_key(rule: TransformationRule) -> str:
    """Builds a stable human-readable key for report buckets."""
    return f"{rule.get_rule_name()} | {rule.old_var_name} -> {rule.new_var_name}"


class RuleApplicationResult(NamedTuple):
    """Encapsulates the result of applying a transformation rule to a dataset.

    Attributes:
        enriched_data (list[dict[str, Any]]): The updated enriched data containing mixed types.
        enriched_mapping (dict[str, str]): The updated header-variable mapping.
        fields_report (list[tuple[str, str]]): Original and transformed string values per row.
        errors_report (list[tuple[str, str | None]]): Errors encountered during transformation.
    """

    enriched_data: list[dict[str, Any]]
    enriched_mapping: dict[str, str]
    fields_report: list[tuple[str, str]]
    errors_report: list[tuple[str, str | None]]


def apply_rule_to_var(
    rule: TransformationRule,
    enriched_data: list[dict[str, Any]],
    enriched_mapping: dict[str, str],
) -> RuleApplicationResult:
    """Applies the given transformation rules to the specified variable in the data."""

    LOGGER.info(
        "Applying transformation rule '%s' to variable '%s'.",
        rule.get_rule_name(),
        rule.old_var_name,
    )

    old_var_name = rule.old_var_name
    new_var_name = rule.new_var_name
    new_header_name = rule.new_header_name
    enriched_mapping[new_var_name] = new_header_name

    fields_report: list[tuple[str, str]] = []
    errors_report: list[tuple[str, str | None]] = []

    for i, data_row in enumerate(enriched_data):
        original_value = data_row.get(old_var_name, "")

        # Always convert to a clean string format for reporting and transformation
        original_value_str = "" if original_value is None else str(original_value)

        # Check explicitly for None or empty string.
        if original_value is None or original_value == "":
            LOGGER.warning(
                "Row %d: Variable '%s' is missing or empty. Skipping transformation.",
                i,
                old_var_name,
            )
            fields_report.append((original_value_str, original_value_str))
            errors_report.append(
                (
                    original_value_str,
                    f"Variable is missing or empty for variable '{old_var_name}' at row {i}.",
                )
            )
            continue

        try:
            # Ensure we are passing a string representation to the transform method
            transformed_value = rule.transform(original_value_str)
            data_row[new_var_name] = transformed_value

            # Fix: Ensure both elements of the tuple are strings to comply with the Pydantic schema
            fields_report.append((original_value_str, str(transformed_value)))
            errors_report.append((original_value_str, None))
        except Exception as e:
            error_msg = str(e) or repr(e)

            LOGGER.error(
                "Error applying transformation rule '%s' to variable '%s' with value '%s': %s",
                rule.get_rule_name(),
                old_var_name,
                original_value_str,
                error_msg,
            )
            # Set empty string for easier detection of transformation errors in the report
            data_row[new_var_name] = ""
            fields_report.append((original_value_str, ""))
            errors_report.append((original_value_str, error_msg))

    LOGGER.info(
        "Completed applying transformation rule '%s' to variable '%s'.",
        rule.get_rule_name(),
        old_var_name,
    )

    return RuleApplicationResult(
        enriched_data=enriched_data,
        enriched_mapping=enriched_mapping,
        fields_report=fields_report,
        errors_report=errors_report,
    )


def map_rules_by_variable(
    rules: list[AnyRule],
) -> dict[str, list[AnyRule]]:
    """Maps transformation rules by their associated variable for quick lookup."""
    LOGGER.info("Mapping transformation rules by their associated variable.")
    rules_mapping: dict[str, list[AnyRule]] = {}
    for rule in rules:
        var_name = rule.old_var_name
        rules_mapping.setdefault(var_name, []).append(rule)
        LOGGER.debug(
            "Mapped transformation rule '%s' to variable '%s'.",
            rule.get_rule_name(),
            var_name,
        )

    # LOGGER.info(
    #     "Completed mapping of transformation rules. %d keys and %d values in mapping result.",
    #     len(rules_mapping.keys()),
    #     len(rules_mapping.values()),
    # )

    return rules_mapping


def transform_data(
    excel_data: list[dict[str, Any]],  # Aligned type hint to Any
    mapping: dict[str, str],
    transformation_rules: list[AnyRule],
) -> DataTransformationReport:
    """Transforms the given Excel data using the provided mapping and rules."""

    enriched_data = copy.deepcopy(excel_data)
    enriched_mapping = copy.deepcopy(mapping)

    LOGGER.info(
        "Starting data transformation with %d rules.", len(transformation_rules)
    )
    LOGGER.info(
        "Transforming %d rows of Excel data and %d mapping entries.",
        len(excel_data),
        len(mapping),
    )

    rules_mapping = map_rules_by_variable(transformation_rules)

    missing_vars_required_by_rules: dict[str, list[AnyRule]] = {}
    var_name_conflicts: list[AnyRule] = []
    field_reports_by_rule: dict[str, list[tuple[str, str]]] = {}
    error_reports_by_rule: dict[str, list[tuple[str, str | None]]] = {}
    fatal_errors: dict[str, str] = {}

    for var_name, mapped_rules in rules_mapping.items():
        LOGGER.info(
            "Applying %d transformation rules to variable '%s'.",
            len(mapped_rules),
            var_name,
        )

        if var_name not in enriched_mapping:
            LOGGER.warning(
                "Variable '%s' from transformation rules is not present in the mapping. Skipping %d associated rules.",
                var_name,
                len(mapped_rules),
            )
            missing_vars_required_by_rules[var_name] = mapped_rules
            continue

        for rule in mapped_rules:
            rule_report_key = _build_rule_report_key(rule)
            new_var_name = rule.new_var_name
            # Check for conflicts with existing variable names in the enriched mapping
            if new_var_name in enriched_mapping:
                LOGGER.error(
                    f"Cannot apply transformation rule '{rule.get_rule_name()}': Variable '{new_var_name}' already exists!",
                )
                var_name_conflicts.append(rule)
                continue

            try:
                result = apply_rule_to_var(rule, enriched_data, enriched_mapping)
                error_reports_by_rule[rule_report_key] = result.errors_report
                field_reports_by_rule[rule_report_key] = result.fields_report
                enriched_data = result.enriched_data
                enriched_mapping = result.enriched_mapping
            except Exception as e:
                LOGGER.error(
                    "Fatal error while applying transformation rule '%s' to variable '%s': %s",
                    rule.get_rule_name(),
                    var_name,
                    e,
                )
                fatal_errors[rule_report_key] = str(e) or repr(e)
                new_header = enriched_mapping.pop(new_var_name, None)
                LOGGER.info(
                    "Removed variable '%s' and its header '%s' from enriched mapping due to fatal error.",
                    new_var_name,
                    new_header,
                )
                removed_transformed_values = []
                for row in enriched_data:
                    removed_value = row.pop(new_var_name, None)
                    removed_transformed_values.append(removed_value)

                LOGGER.info(
                    "Removed %d transformed values for variable '%s' from enriched data due to fatal error",
                    len(removed_transformed_values),
                    new_var_name,
                )

    transformation_report = DataTransformationReport(
        enriched_variable_to_readable_mapping=enriched_mapping,
        enriched_data=enriched_data,
        applied_rules=transformation_rules,
        missing_vars_required_by_rules=missing_vars_required_by_rules,
        var_name_conflicts=var_name_conflicts,
        field_reports_by_rule=field_reports_by_rule,
        error_reports_by_rule=error_reports_by_rule,
        fatal_errors=fatal_errors,
    )

    return transformation_report
