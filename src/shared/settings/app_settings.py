from typing import Union, Annotated
from pydantic import BaseModel, Field

# fmt: off
from src.core.data_transformation.transformation_rules.num_to_words_rule import NumToWordsRule
from src.core.data_transformation.transformation_rules.name_declension_rule import NameDeclensionRule
from src.core.data_transformation.transformation_rules.date_part_getter_rule import DatePartGetterRule
from src.core.data_transformation.transformation_rules.name_part_getter_rule import NamePartGetterRule
from src.core.data_transformation.transformation_rules.name_shortener_rule import NameShortenerRule
# fmt: on

AnyRule = Annotated[
    Union[
        NumToWordsRule,
        NameDeclensionRule,
        DatePartGetterRule,
        NamePartGetterRule,
        NameShortenerRule,
    ],
    Field(discriminator="type"),
]


class AppSettings(BaseModel):
    """Represents the application settings.

    Fields:
        rules_list (list[AnyRule]): A list of transformation rules.
    """

    rules_list: list[AnyRule] = Field(
        default_factory=list, description="List of transformation rules"
    )
