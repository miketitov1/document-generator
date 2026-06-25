from typing import ClassVar, Literal, override, Any
from pydantic import Field, PrivateAttr, field_validator

from src.core.data_transformation.transformation_rule import TransformationRule
from src.core.data_transformation.common_enums import PytrovichLanguages

from pytrovich.maker import PetrovichDeclinationMaker
from pytrovich.detector import PetrovichGenderDetector
from pytrovich.enums import NamePart, Case


class NameDeclensionRule(TransformationRule):
    """A transformation rule that applies name declension."""

    type: Literal["name_declension"] = "name_declension"

    lang: PytrovichLanguages = Field(
        default=PytrovichLanguages.RUSSIAN, title="Language", description="Language of the name."
    )
    case: Case = Field(
        default=Case.GENITIVE, title="Case", description="Target grammatical case."
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
    # SUPPORTED_CASES: ClassVar[dict[Case, str]] = {
    #     Case.GENITIVE: "Genitive case",
    #     Case.DATIVE: "Dative case",
    #     Case.ACCUSATIVE: "Accusative case",
    #     Case.INSTRUMENTAL: "Instrumental case",
    #     Case.PREPOSITIONAL: "Prepositional case",
    # }

    _maker: PetrovichDeclinationMaker = PrivateAttr()
    _gender_detector: PetrovichGenderDetector = PrivateAttr()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Initialize stateless helpers after Pydantic validation completes
        self._maker = PetrovichDeclinationMaker()
        self._gender_detector = PetrovichGenderDetector()

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: PytrovichLanguages) -> PytrovichLanguages:
        if v not in PytrovichLanguages:
            raise ValueError(f"Unsupported language '{v}' for name declension rule.")
        return v

    @field_validator("name_parts_order")
    @classmethod
    def validate_name_parts_order(cls, v: list[NamePart]) -> list[NamePart]:
        expected = {NamePart.LASTNAME, NamePart.FIRSTNAME, NamePart.MIDDLENAME}
        if len(v) != 3 or set(v) != expected:
            raise ValueError(
                f"name_parts_order must contain exactly LASTNAME, FIRSTNAME, MIDDLENAME. Got: {v}"
            )
        return v

    @override
    def default_var_rename(self, old_var_name: str) -> str:
        return f"{old_var_name}_{self.case.name.lower()}_case"

    @override
    def default_header_rename(self, old_header_name: str) -> str:
        return f"{old_header_name} ({self.case.name.lower()} case)"

    @override
    @classmethod
    def get_rule_name(cls) -> str:
        return "Name Declension"

    @override
    def transform(self, value: str) -> str:
        """Transforms a full name string by declining it to the target case."""
        if not value:
            raise ValueError("Input value for NameDeclensionRule cannot be empty.")

        parts = value.split()
        if len(parts) != 3:
            raise ValueError(
                f"NameDeclensionRule expected 3 name parts, got {len(parts)} for value '{value}'."
            )

        name_map = dict(zip(self.name_parts_order, parts))

        lastname = name_map.get(NamePart.LASTNAME)
        firstname = name_map.get(NamePart.FIRSTNAME)
        middlename = name_map.get(NamePart.MIDDLENAME)

        if not (lastname and firstname and middlename):
            raise ValueError(
                f"Failed to map name parts for value '{value}'. Expected: {self.name_parts_order}. Got: {parts}"
            )

        gender = None
        try:
            gender = self._gender_detector.detect(
                lastname=lastname, firstname=firstname, middlename=middlename
            )

            declined_parts = []
            for part_type in self.name_parts_order:
                declined_parts.append(
                    self._maker.make(part_type, gender, self.case, name_map[part_type])
                )

        except Exception as e:
            error_msg = str(e) or repr(e)
            raise ValueError(
                f"Failed to decline name firstname={firstname}, middlename={middlename}, lastname={lastname}, gender={gender} because of {error_msg}"
            ) from e

        return " ".join(declined_parts)
