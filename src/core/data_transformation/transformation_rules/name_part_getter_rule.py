from typing import ClassVar, override, Literal
from pydantic import Field, field_validator
from pytrovich.enums import NamePart

from src.core.data_transformation.transformation_rule import TransformationRule
from src.core.data_transformation.common_enums import PytrovichLanguages


class NamePartGetterRule(TransformationRule):
    """Transformation rule that extracts a specific part of a name (first name, last name, etc.)."""

    type: Literal["name_part_getter"] = "name_part_getter"
    lang: PytrovichLanguages = Field(
        default=PytrovichLanguages.RUSSIAN, title="Language", description="Language of the name."
    )
    name_part: NamePart = Field(
        default=NamePart.FIRSTNAME, title="Name Part", description="Target name part."
    )
    name_parts_order: list[NamePart] = Field(
        default_factory=lambda: [
            NamePart.LASTNAME,
            NamePart.FIRSTNAME,
            NamePart.MIDDLENAME,
        ],
        title="Name Parts Order",
        description="Order of name parts (Last, First, Middle).",
    )

    # Kept for UI/reference purposes; Pydantic handles enum validation natively
    # SUPPORTED_LANGUAGES: ClassVar[dict[PytrovichSupportedLanguages, str]] = {PytrovichSupportedLanguages.RUSSIAN: "Russian"}
    # SUPPORTED_NAME_PARTS: ClassVar[dict[NamePart, str]] = {
    #     NamePart.LASTNAME: "Last name",
    #     NamePart.FIRSTNAME: "First name",
    #     NamePart.MIDDLENAME: "Middle name",
    # }

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: PytrovichLanguages) -> PytrovichLanguages:
        if v not in PytrovichLanguages:
            raise ValueError(f"Unsupported language '{v}' for name part getter rule.")
        return v

    @field_validator("name_parts_order")
    @classmethod
    def validate_name_parts_order(cls, v: list[NamePart]) -> list[NamePart]:
        expected = {NamePart.LASTNAME, NamePart.FIRSTNAME, NamePart.MIDDLENAME}
        if (len(v) != len(expected)) or (set(v) != expected):
            raise ValueError(
                f"Name parts order must contain exactly LASTNAME, FIRSTNAME, MIDDLENAME. Got: {v}"
            )
        return v

    @override
    def default_var_rename(self, old_var_name: str) -> str:
        return f"{old_var_name}_{self.name_part.name.lower()}"

    @override
    def default_header_rename(self, old_header_name: str) -> str:
        return f"{old_header_name} ({self.name_part.name.lower()})"

    @override
    @classmethod
    def get_rule_name(cls) -> str:
        return "Name Part Getter"

    @override
    def transform(self, value: str) -> str:
        """Extracts the specified part of the name from the given value."""
        if not value:
            raise ValueError("Input value for NamePartGetterRule cannot be empty.")

        parts = value.split()
        if len(parts) != 3:
            raise ValueError(
                f"NamePartGetterRule expected 3 name parts, got {len(parts)} for value '{value}'."
            )

        name_map = dict(zip(self.name_parts_order, parts))
        return name_map.get(self.name_part, "")
