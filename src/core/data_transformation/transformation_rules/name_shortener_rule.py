from typing import ClassVar, override, Literal
from pydantic import Field, field_validator
from pytrovich.enums import NamePart

from src.core.data_transformation.transformation_rule import TransformationRule
from src.core.data_transformation.common_enums import PytrovichLanguages


class NameShortenerRule(TransformationRule):
    """Transformation rule that shortens a name by keeping only the specified name part (first name, last name, etc.)."""

    type: Literal["name_shortener"] = "name_shortener"
    lang: PytrovichLanguages = Field(
        default=PytrovichLanguages.RUSSIAN, title="Language", description="Language of the name."
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

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: PytrovichLanguages) -> PytrovichLanguages:
        if v not in PytrovichLanguages:
            raise ValueError(f"Unsupported language '{v}' for name shortener rule.")
        return v

    @field_validator("name_parts_order")
    @classmethod
    def validate_name_parts_order(cls, v: list[NamePart]) -> list[NamePart]:
        expected = {NamePart.LASTNAME, NamePart.FIRSTNAME, NamePart.MIDDLENAME}
        if (len(v) != len(expected)) or (set(v) != expected):
            raise ValueError(
                f"name_parts_order must contain exactly LASTNAME, FIRSTNAME, MIDDLENAME. Got: {v}"
            )
        return v

    @override
    def default_var_rename(self, old_var_name: str) -> str:
        return f"{old_var_name}_short_name"

    @override
    def default_header_rename(self, old_header_name: str) -> str:
        return f"{old_header_name} (short name)"

    @override
    @classmethod
    def get_rule_name(cls) -> str:
        return "Name Shortener"

    @override
    def transform(self, value: str) -> str:
        if not value:
            raise ValueError("Input value for NameShortenerRule cannot be empty.")

        name_parts = value.split()
        if len(name_parts) != 3:
            raise ValueError(
                f"Expected full name with 3 parts but got {len(name_parts)} parts in '{value}'"
            )

        name_map = dict(zip(self.name_parts_order, name_parts))

        first_name = name_map.get(NamePart.FIRSTNAME, "")
        last_name = name_map.get(NamePart.LASTNAME, "")
        middlename = name_map.get(NamePart.MIDDLENAME, "")

        return f"{last_name} {first_name[0]}. {middlename[0]}."
