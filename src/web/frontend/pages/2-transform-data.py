from __future__ import annotations

import json

import pandas as pd
import requests
import streamlit as st

from src.core.data_loading.data_loader_report import DataLoaderReport
from src.core.data_transformation.data_transformation_report import (
	DataTransformationReport,
)
from src.shared.settings.app_settings import AppSettings, AnyRule

FASTAPI_URL = "http://localhost:8000"
SETTINGS_ENDPOINT = f"{FASTAPI_URL}/settings"
TRANSFORM_ENDPOINT = f"{FASTAPI_URL}/transform-data"
TRANSFORM_REPORT_STATE_KEY = "transform_report"
TRANSFORM_SOURCE_FILENAME_STATE_KEY = "transform_source_filename"
TRANSFORM_RULES_SIGNATURE_STATE_KEY = "transform_rules_signature"
BASE_RULE_KEYS = {
	"selected",
	"old_var_name",
	"old_header_name",
	"new_var_name",
	"new_header_name",
	"type",
	"rule_type",
}


def fetch_settings() -> AppSettings | None:
	"""Fetches the application settings from the backend.

	Returns:
		AppSettings | None: The validated settings model, or None when the request fails.
	"""
	try:
		response = requests.get(SETTINGS_ENDPOINT, timeout=30)
		response.raise_for_status()
		return AppSettings.model_validate(response.json())
	except (requests.RequestException, ValueError) as exc:
		st.error(f"Failed to fetch transformation settings: {exc}")
		return None


def get_source_report() -> DataLoaderReport | None:
	"""Reads the loaded-data report from session state.

	Returns:
		DataLoaderReport | None: The source report if present and valid.
	"""
	report = st.session_state.get("report")
	if isinstance(report, DataLoaderReport):
		return report
	return None


def get_selected_rules(settings: AppSettings | None) -> list[AnyRule]:
	"""Extracts the selected transformation rules from settings.

	Args:
		settings (AppSettings | None): The fetched application settings.

	Returns:
		list[AnyRule]: The selected transformation rules.
	"""
	if settings is None:
		return []
	return [rule for rule in settings.rules_list if rule.selected]


def build_rules_signature(rules: list[AnyRule]) -> str:
	"""Builds a JSON-safe signature for the selected rules.

	Args:
		rules (list[AnyRule]): The selected transformation rules.

	Returns:
		str: A stable signature string.
	"""
	dumped_rules = [rule.model_dump(mode="json") for rule in rules]
	return json.dumps(dumped_rules, sort_keys=True)


def invalidate_stale_transform_report(
	source_report: DataLoaderReport | None,
	selected_rules_signature: str | None,
) -> None:
	"""Clears stale transform results when the source data or rules changed.

	Args:
		source_report (DataLoaderReport | None): The current source report.
		selected_rules_signature (str | None): Signature of the selected rules.
	"""
	stored_filename = st.session_state.get(TRANSFORM_SOURCE_FILENAME_STATE_KEY)
	stored_signature = st.session_state.get(TRANSFORM_RULES_SIGNATURE_STATE_KEY)
	stored_report = st.session_state.get(TRANSFORM_REPORT_STATE_KEY)

	if source_report is None:
		if stored_report is not None:
			st.session_state.pop(TRANSFORM_REPORT_STATE_KEY, None)
			st.session_state.pop(TRANSFORM_SOURCE_FILENAME_STATE_KEY, None)
			st.session_state.pop(TRANSFORM_RULES_SIGNATURE_STATE_KEY, None)
		return

	if stored_filename != source_report.filename:
		st.session_state.pop(TRANSFORM_REPORT_STATE_KEY, None)
		st.session_state.pop(TRANSFORM_SOURCE_FILENAME_STATE_KEY, None)
		st.session_state.pop(TRANSFORM_RULES_SIGNATURE_STATE_KEY, None)
		return

	if (selected_rules_signature is not None) and (stored_signature != selected_rules_signature):
		st.session_state.pop(TRANSFORM_REPORT_STATE_KEY, None)
		st.session_state.pop(TRANSFORM_SOURCE_FILENAME_STATE_KEY, None)
		st.session_state.pop(TRANSFORM_RULES_SIGNATURE_STATE_KEY, None)


def rule_to_row(rule: AnyRule) -> dict[str, str | bool]:
	"""Converts a transformation rule into a display row.

	Args:
		rule (AnyRule): The rule to summarize.

	Returns:
		dict[str, str | bool]: A display-friendly representation of the rule.
	"""
	rule_dump = rule.model_dump(mode="json")
	extra_fields = [
		f"{name}={value}"
		for name, value in rule_dump.items()
		if name not in BASE_RULE_KEYS
	]
	return {
		"Selected": rule.selected,
		"Type": rule.get_rule_name(),
		"Old Variable": rule.old_var_name,
		"Old Header": rule.old_header_name,
		"New Variable": rule.new_var_name,
		"New Header": rule.new_header_name,
		"Extra Parameters": ", ".join(extra_fields) if extra_fields else "-",
	}


def render_selected_rules(rules: list[AnyRule]) -> None:
	"""Renders the selected transformation rules above the tab section.

	Args:
		rules (list[AnyRule]): The selected transformation rules.
	"""
	st.subheader("Selected Transformation Rules")
	if not rules:
		st.info("No transformation rules are currently selected in settings.")
		return

	st.caption("These are fetched from the backend via GET /settings.")
	rules_df = pd.DataFrame([rule_to_row(rule) for rule in rules])
	st.dataframe(rules_df, use_container_width=True, hide_index=True)


def transform_source_data(source_report: DataLoaderReport) -> DataTransformationReport:
	"""Sends the loaded data to the backend and returns the transformation report.

	Args:
		source_report (DataLoaderReport): The loaded data report from page 1.

	Returns:
		DataTransformationReport: The transformation report returned by the API.

	Raises:
		requests.RequestException: If the backend request fails.
	"""
	with st.spinner("Transforming loaded data..."):
		response = requests.post(
			TRANSFORM_ENDPOINT,
			json=source_report.model_dump(mode="json"),
			timeout=120,
		)
		response.raise_for_status()

	return DataTransformationReport.model_validate(response.json())


def get_new_column_names(
	report: DataTransformationReport,
	source_report: DataLoaderReport | None,
) -> list[str]:
	"""Computes the new transformed columns that should be displayed.

	Args:
		report (DataTransformationReport): The transformation report.
		source_report (DataLoaderReport | None): The original loaded data report.

	Returns:
		list[str]: The transformed column names only.
	"""
	if not report.enriched_data:
		return []

	available_columns = list(report.enriched_data[0].keys())
	if source_report is not None:
		source_columns = set(source_report.variable_to_readable_mapping.keys())
		return [column for column in available_columns if column not in source_columns]

	transformed_columns = {rule.new_var_name for rule in report.applied_rules}
	return [column for column in available_columns if column in transformed_columns]


def render_transformed_data_tab(
	report: DataTransformationReport,
	source_report: DataLoaderReport | None,
) -> None:
	"""Renders the transformed columns preview tab.

	Args:
		report (DataTransformationReport): The transformation report.
		source_report (DataLoaderReport | None): The original loaded data report.
	"""
	st.subheader("New Transformed Columns")

	if not report.enriched_data:
		st.info("No transformed rows are available yet.")
		return

	transformed_columns = get_new_column_names(report, source_report)
	if not transformed_columns:
		st.info("No new columns were produced by the selected transformation rules.")
		return

	transformed_df = pd.DataFrame(report.enriched_data)
	st.dataframe(
		transformed_df[transformed_columns],
		use_container_width=True,
		hide_index=True,
	)


def render_mapping_tab(report: DataTransformationReport) -> None:
	"""Renders the transformed variable-to-readable-name mapping tab.

	Args:
		report (DataTransformationReport): The transformation report.
	"""
	st.subheader("Variable Name to Readable Name Mapping")

	if not report.enriched_variable_to_readable_mapping:
		st.info("No mapping entries are available yet.")
		return

	mapping_df = pd.DataFrame(
		[
			{"Variable Name": variable_name, "Readable Name": readable_name}
			for variable_name, readable_name in report.enriched_variable_to_readable_mapping.items()
		]
	)
	st.dataframe(mapping_df, use_container_width=True, hide_index=True)


def render_rule_occurrence_table(
	title: str,
	rows: list[dict[str, str]],
	empty_message: str,
) -> None:
	"""Renders a table section used by the issues tab.

	Args:
		title (str): The section title.
		rows (list[dict[str, str]]): The rows to display.
		empty_message (str): Message shown when there are no rows.
	"""
	st.markdown(f"#### {title}")
	if not rows:
		st.info(empty_message)
		return

	st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_issues_tab(report: DataTransformationReport) -> None:
	"""Renders the comprehensive transformation issues tab.

	Args:
		report (DataTransformationReport): The transformation report.
	"""
	st.subheader("Transformation Issues")

	if not report.any_errors:
		st.success("No transformation issues were detected.")
		return

	if report.any_missing_vars:
		missing_rows = [
			{
				"Missing Variable": missing_var,
				"Affected Rule": str(rule),
			}
			for missing_var, rules in report.missing_vars_required_by_rules.items()
			for rule in rules
		]
		render_rule_occurrence_table(
			"Missing Variables",
			missing_rows,
			"No missing variables were recorded.",
		)

	if report.any_var_name_conflicts:
		conflict_rows = [
			{
				"Conflicting Rule": str(rule),
				"Conflict": f"New variable '{rule.new_var_name}' already exists.",
			}
			for rule in report.var_name_conflicts
		]
		render_rule_occurrence_table(
			"Variable Name Conflicts",
			conflict_rows,
			"No variable name conflicts were recorded.",
		)

	if report.any_error_reports:
		error_rows: list[dict[str, str]] = []
		for rule_name, rows in report.error_reports_by_rule.items():
			for row_index, (original_value, error_message) in enumerate(rows, start=1):
				error_rows.append(
					{
						"Rule": rule_name,
						"Row": str(row_index),
						"Original Value": original_value or "",
						"Status": "Error" if error_message else "OK",
						"Message": error_message or "-",
					}
				)
		render_rule_occurrence_table(
			"Row-Level Transformation Results",
			error_rows,
			"No row-level transformation results were recorded.",
		)

	if report.any_fatal_errors:
		fatal_rows = [
			{"Rule": rule_name, "Message": error_message}
			for rule_name, error_message in report.fatal_errors.items()
		]
		render_rule_occurrence_table(
			"Fatal Errors",
			fatal_rows,
			"No fatal errors were recorded.",
		)


def main() -> None:
	"""Main entry point for the transform-data page.

	The page fetches selected rules from the backend, lets the user run the
	transformation for the loaded file, and keeps the resulting report in
	session state.
	"""
	st.set_page_config(page_title="Transform Data", page_icon="🔄")
	st.title("🔄 Transform Loaded Data")

	source_report = get_source_report()
	settings = fetch_settings()
	selected_rules = get_selected_rules(settings)
	selected_rules_signature = build_rules_signature(selected_rules) if settings is not None else None

	invalidate_stale_transform_report(source_report, selected_rules_signature)
	render_selected_rules(selected_rules)

	if source_report is None:
		st.info("Load and analyze an Excel file on the data loading page first.")
		return

	if selected_rules:
		st.caption(f"{len(selected_rules)} selected transformation rule(s) are available to run.")
	else:
		st.warning("No transformation rules are selected right now. The transform button will still return the current data snapshot.")

	if st.button("Transform Data", type="primary"):
		try:
			transformed_report = transform_source_data(source_report)
			st.session_state[TRANSFORM_REPORT_STATE_KEY] = transformed_report
			st.session_state[TRANSFORM_SOURCE_FILENAME_STATE_KEY] = source_report.filename
			st.session_state[TRANSFORM_RULES_SIGNATURE_STATE_KEY] = selected_rules_signature
			st.success(f"Successfully transformed: **{source_report.filename}**")
		except requests.RequestException as exc:
			st.error(f"Failed to transform data: {exc}")
		except Exception as exc:
			st.error(f"Unexpected transformation error: {exc}")

	transform_report = st.session_state.get(TRANSFORM_REPORT_STATE_KEY)
	if isinstance(transform_report, DataTransformationReport):
		st.divider()
		tab_data, tab_mapping, tab_issues = st.tabs(
			["🧩 Transformed Columns", "🗺️ Variable Mapping", "⚠️ Issues"]
		)

		with tab_data:
			render_transformed_data_tab(transform_report, source_report)

		with tab_mapping:
			render_mapping_tab(transform_report)

		with tab_issues:
			render_issues_tab(transform_report)


if __name__ == "__main__":
	main()



