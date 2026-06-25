from enum import Enum
from typing import ClassVar, override, Literal
from dateutil import parser
from pydantic import Field, field_validator

from src.core.data_transformation.transformation_rule import TransformationRule


class DatePart(str, Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"

    @property
    def label(self) -> str:
        """Returns the human-readable label for the date part."""
        SUPPORTED_PARTS: dict[DatePart, str] = {
            DatePart.DAY: "day",
            DatePart.MONTH: "month",
            DatePart.YEAR: "year",
        }
        return SUPPORTED_PARTS.get(self, self.name)


class DatePartGetterRule(TransformationRule):
    """
    Transformation rule that extracts a specific part of a date (day, month, year).
    """

    type: Literal["date_part_getter"] = "date_part_getter"

    date_part: DatePart = Field(
        default=DatePart.DAY,
        title="Date Part",
        description="Date part to extract from the date string.",
    )

    @field_validator("date_part")
    @classmethod
    def validate_date_part(cls, v: DatePart) -> DatePart:
        if v not in DatePart:
            raise ValueError(f"Unsupported date part '{v}' for date part getter rule.")
        return v

    @override
    def default_var_rename(self, old_var_name: str) -> str:
        new_var_name = f"{old_var_name.replace('_date', '')}_{self.date_part.label}"
        return new_var_name

    @override
    def default_header_rename(self, old_header_name: str) -> str:
        new_header_name = f"{old_header_name} ({self.date_part.label})"
        return new_header_name

    @override
    @classmethod
    def get_rule_name(cls) -> str:
        return "Date Part Getter"

    @override
    def transform(self, value: str) -> str:
        """
        Extracts the specified part of the date from the given value.

        Args:
            value (str): The date string to extract the part from.
        Returns:
            str: The extracted date part as a string.
        """
        if not value:
            raise ValueError("Input value for DatePartGetterRule cannot be empty.")

        date = parser.parse(value)
        if self.date_part == DatePart.DAY:
            return str(date.day)
        elif self.date_part == DatePart.MONTH:
            return str(date.month)
        elif self.date_part == DatePart.YEAR:
            return str(date.year)
        else:
            raise ValueError(f"Unsupported date part: '{self.date_part}'")