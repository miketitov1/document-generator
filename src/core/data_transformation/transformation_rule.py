from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, model_validator


class TransformationRule(BaseModel, ABC):
    """Base class for transformation rules.

    This class defines the interface and common functionality for all data
    transformation rules applied to variables from the data source.

    Attributes:
        selected (bool): Indicates whether the rule is selected.
        old_var_name (str): The variable name in the data source to be transformed.
        old_header_name (str): The column header in the Excel file.
        new_var_name (str): Valid python variable name for the transformed value.
        new_header_name (str): Name for the transformed column header.
    """

    selected: bool = Field(
        default=False,
        title="Selected",
        description="Indicates whether the rule is selected.",
    )
    old_var_name: str = Field(
        title="Old Variable Name",
        description="The variable name in the data source to be transformed.",
    )
    old_header_name: str = Field(
        title="Old Header Name",
        description="The column header in the Excel file.",
    )
    new_var_name: str = Field(
        default="",
        title="New Variable Name",
        description="Optional: valid python variable name for the transformed value.",
    )
    new_header_name: str = Field(
        default="",
        title="New Header Name",
        description="Optional: name for the transformed column header.",
    )

    @model_validator(mode="after")
    def apply_default_renames(self) -> "TransformationRule":
        """Automatically generate new names if they are not provided or empty.

        Returns:
            TransformationRule: The updated instance with default names applied.

        Raises:
            ValueError: If the new variable name is identical to the old one.
        """
        if self.new_var_name == self.old_var_name:
            raise ValueError(
                f"New variable name cannot be the same as the old variable name: {self.old_var_name}"
            )
        if not self.new_var_name:
            self.new_var_name = self.default_var_rename(self.old_var_name)
        if not self.new_header_name:
            self.new_header_name = self.default_header_rename(self.old_header_name)
        return self

    @abstractmethod
    def default_var_rename(self, old_var_name: str) -> str:
        """Renames the variable name according to the rule defaults.

        Args:
            old_var_name (str): The original variable name.

        Returns:
            str: The new transformed variable name.
        """
        pass

    @abstractmethod
    def default_header_rename(self, old_header_name: str) -> str:
        """Renames the header according to the rule defaults.

        Args:
            old_header_name (str): The original header name.

        Returns:
            str: The new transformed header name.
        """
        pass

    @classmethod
    @abstractmethod
    def get_rule_name(cls) -> str:
        """Returns a human-readable name for the transformation rule.

        Returns:
            str: A string representing the rule type.
        """
        pass

    def __str__(self) -> str:
        """Returns a formatted string representation of the transformation rule.

        Returns:
            str: Rule details including selection status and name mapping.
        """
        return (
            f"{self.get_rule_name()} (selected='{self.selected}', "
            f"old_var='{self.old_var_name}', old_header='{self.old_header_name}', "
            f"new_var='{self.new_var_name}', new_header='{self.new_header_name}')"
        )

    @abstractmethod
    def transform(self, value: str) -> str:
        """Transforms the input value according to the rule.

        Args:
            value (str): The raw string value to be transformed.

        Returns:
            str: The transformed string value.
        """
        pass

    @classmethod
    def get_rule_classes(cls) -> dict[str, type["TransformationRule"]]:
        """Retrieves a dictionary of available transformation rule classes.

        Returns:
            dict[str, type[TransformationRule]]: A mapping of rule names to their respective classes.
        """
        # fmt: off
        from src.core.data_transformation.transformation_rules.num_to_words_rule import NumToWordsRule
        from src.core.data_transformation.transformation_rules.name_declension_rule import NameDeclensionRule
        from src.core.data_transformation.transformation_rules.date_part_getter_rule import DatePartGetterRule
        from src.core.data_transformation.transformation_rules.name_part_getter_rule import NamePartGetterRule
        from src.core.data_transformation.transformation_rules.name_shortener_rule import NameShortenerRule
        # fmt: on

        return {
            NumToWordsRule.get_rule_name(): NumToWordsRule,
            NameDeclensionRule.get_rule_name(): NameDeclensionRule,
            DatePartGetterRule.get_rule_name(): DatePartGetterRule,
            NamePartGetterRule.get_rule_name(): NamePartGetterRule,
            NameShortenerRule.get_rule_name(): NameShortenerRule,
        }
    
    # @classmethod
    # def get_schema(cls) -> dict[str, dict[str, Any]]:
    #     """
    #     Dynamically generates a schema dictionary based on Pydantic fields.
    #     Subclasses no longer need to override this!
    #     """

    #     schema = {}
    #     for name, field_info in cls.model_fields.items():
    #         schema[name] = {
    #             "label": field_info.title or name.replace("_", " ").title(),
    #             "type": field_info.annotation,
    #             "required": field_info.is_required(),
    #             "help": field_info.description,
    #         }
    #     return schema

    #     return cls.model_json_schema()