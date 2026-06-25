import logging
from typing import IO, Any, cast
from pathlib import Path
from numbers import Integral

import pandas as pd
import numpy as np

from src.core.data_loading.data_loader_report import DataLoaderReport

LOGGER = logging.getLogger(__name__)

INCOMING_DATA_TYPE = str | Path | IO[bytes]

_MIN_ARROW_INT64 = -(2**63)
_MAX_ARROW_INT64 = 2**63 - 1

# TODO: Change loading behaviour to account for date formatting issues
# TODO: Refactor for async support
# TODO: Strip space around var names to avoid the app treating "full_name" and "full_name " differently
def load_data(source: INCOMING_DATA_TYPE, source_name: str) -> DataLoaderReport:

    LOGGER.info(
        "Loading data from source of type %s and name: %s",
        type(source).__name__,
        source_name,
    )

    # 1. Build the mapping from readable names to variable names
    (
        variable_to_readable_mapping,
        missing_variable_names,
        missing_readable_names,
        duplicate_readable_names,
        duplicate_variable_names,
    ) = _build_readable_to_variable_name_mapping(source)

    # 2. Read the actual data
    duplicate_variable_names_indices = [idx for idx, _ in duplicate_variable_names]
    columns_to_drop = missing_variable_names + duplicate_variable_names_indices
    loaded_data, missing_row_column_fields = _read_data(
        source, columns_to_drop, skiprows=[0]
    )

    # 3. Build the report
    # Handle missing values (NaN) so JSON doesn't crash
    # This replaces NaN with None, which FastAPI safely converts to JSON 'null'
    loaded_data = loaded_data.replace({np.nan: None})
    loaded_data_dicts = cast(list[dict[str, Any]], loaded_data.to_dict(orient="records"))

    loader_report = DataLoaderReport(
        filename=source_name,
        variable_to_readable_mapping=variable_to_readable_mapping,
        loaded_data=loaded_data_dicts,
        missing_readable_names=missing_readable_names,
        missing_variable_names=missing_variable_names,
        duplicate_readable_names=duplicate_readable_names,
        duplicate_variable_names=duplicate_variable_names,
        missing_row_column_fields=missing_row_column_fields,
    )

    return loader_report


def _build_readable_to_variable_name_mapping(
    source: INCOMING_DATA_TYPE,
) -> tuple[
    dict[str, str], list[int], list[int], list[tuple[int, str]], list[tuple[int, str]]
]:
    LOGGER.info("Building readable to variable name mapping...")
    # Read just the first two rows to build the mapping (readable name -> variable name)
    header_df = pd.read_excel(source, nrows=2, header=None)

    variable_to_readable_mapping = {}
    missing_variable_names = []
    missing_readable_names = []

    duplicate_variable_names = []
    duplicate_readable_names = []

    seen_variable_names = set()
    seen_readable_names = set()

    for col_idx in range(header_df.shape[1]):
        LOGGER.debug("Processing column index %d...", col_idx)
        readable_name = header_df.iat[0, col_idx]
        variable_name = header_df.iat[1, col_idx]

        # ==========================================
        # 1. HANDLE VARIABLE NAME
        # ==========================================
        if pd.isna(variable_name):
            # Skip this column since it doesn't have a variable name
            missing_variable_names.append(col_idx)
            LOGGER.error(
                "Column index %d is missing a variable name. This column will be skipped.",
                col_idx,
            )
            continue

        if variable_name in seen_variable_names:
            # Skip this column since it doesn't have a unique variable name (we won't be able to reference it in the .docx template)
            LOGGER.error(
                "Column index %d contains non-unique variable name '%s'. This column will be skipped.",
                col_idx,
                variable_name,
            )
            duplicate_variable_names.append((col_idx, variable_name))
            continue

        seen_variable_names.add(variable_name)

        # ==========================================
        # 2. HANDLE READABLE NAME
        # ==========================================
        if pd.isna(readable_name):
            # If readable name is missing, rename to "unnamed_{col_idx}" and log a warning
            missing_readable_names.append(col_idx)
            readable_name = f"unnamed_{col_idx}"
            LOGGER.warning(
                "Column index %d is missing a readable name. Renamed to '%s'.",
                col_idx,
                readable_name,
            )

        if readable_name in seen_readable_names:
            old_readable_name = readable_name
            readable_name = f"{readable_name}_{col_idx}"
            LOGGER.warning(
                "Column index %d contains non-unique readable name '%s'. Renamed to '%s'.",
                col_idx,
                old_readable_name,
                readable_name,
            )
            duplicate_readable_names.append((col_idx, old_readable_name))

        seen_readable_names.add(readable_name)

        # ==========================================
        # 3. BUILD THE MAPPING
        # ==========================================
        variable_to_readable_mapping[str(variable_name)] = str(readable_name)

    LOGGER.info(
        "Finished building mapping. Size of mapping: %d. Found %d missing variable names, %d missing readable names, %d duplicate variable names, and %d duplicate readable names.",
        len(variable_to_readable_mapping),
        len(missing_variable_names),
        len(missing_readable_names),
        len(duplicate_variable_names),
        len(duplicate_readable_names),
    )

    return (
        variable_to_readable_mapping,
        missing_variable_names,
        missing_readable_names,
        duplicate_readable_names,
        duplicate_variable_names,
    )


def _read_data(
    source: INCOMING_DATA_TYPE,
    columns_to_drop: list[int],
    skiprows: list[int] = [0],
) -> tuple[pd.DataFrame, list[tuple[int, int]]]:
    LOGGER.info(
        "Reading data..",
    )
    # Read the actual data. Skip the first row (index 0),
    # so pandas uses row index 1 (variable names) as the column headers.
    loaded_data = pd.read_excel(source, skiprows=skiprows)

    missing_row_column_fields = []

    # First we drop any columns that have missing or duplicate variable names, since we won't be able to use them
    loaded_data.drop(loaded_data.columns[columns_to_drop], axis=1, inplace=True)
    if columns_to_drop:
        LOGGER.info(
            "Dropped columns with indices: %s due to missing or duplicate variable names.",
            columns_to_drop,
        )
    else:
        LOGGER.info("No columns dropped since there were no missing or duplicate variable names.")

    for row_idx in range(loaded_data.shape[0]):
        for col_idx in range(loaded_data.shape[1]):
            field_value = loaded_data.iat[row_idx, col_idx]
            
            # Handle missing fields
            if pd.isna(field_value):
                missing_row_column_fields.append((row_idx, col_idx))
                LOGGER.warning(
                    "Missing field at row index %d and column index %d.",
                    row_idx,
                    col_idx,
                )
                continue

            # Handle large integers that might overflow in frontend/JSON (Arrow compatibility)
            if isinstance(field_value, Integral) and not isinstance(field_value, bool):
                try:
                    numeric_value = int(field_value)
                    if numeric_value < _MIN_ARROW_INT64 or numeric_value > _MAX_ARROW_INT64:
                        loaded_data.iat[row_idx, col_idx] = str(numeric_value)
                except (ValueError, OverflowError):
                    loaded_data.iat[row_idx, col_idx] = str(field_value)

    # Convert all datetime columns to a readable string format before returning
    for col in loaded_data.columns:
        if pd.api.types.is_datetime64_any_dtype(loaded_data[col]):
            loaded_data[col] = loaded_data[col].dt.strftime("%Y-%m-%d")

    LOGGER.info(
        "Finished reading data. Data shape: %s. Found %d missing fields.",
        loaded_data.shape,
        len(missing_row_column_fields),
    )

    return loaded_data, missing_row_column_fields
