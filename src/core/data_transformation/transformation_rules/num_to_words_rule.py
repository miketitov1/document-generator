from __future__ import annotations

from enum import Enum
from typing import override, Literal

import num2words
from pydantic import Field, field_validator

from src.core.data_transformation.transformation_rule import TransformationRule


class NumToWordsLanguages(str, Enum):
    en = "en"
    am = "am"
    ar = "ar"
    az = "az"
    be = "be"
    bn = "bn"
    ca = "ca"
    ce = "ce"
    cs = "cs"
    cy = "cy"
    da = "da"
    de = "de"
    en_GB = "en_GB"
    en_IN = "en_IN"
    en_NG = "en_NG"
    es = "es"
    es_CO = "es_CO"
    es_CR = "es_CR"
    es_GT = "es_GT"
    es_VE = "es_VE"
    eu = "eu"
    fa = "fa"
    fi = "fi"
    fr = "fr"
    fr_BE = "fr_BE"
    fr_CH = "fr_CH"
    fr_DZ = "fr_DZ"
    he = "he"
    hi = "hi"
    hu = "hu"
    hy = "hy"
    id = "id"
    # ic instead of is to avoid conflict with the built-in `is` keyword
    ic = "is"
    it = "it"
    ja = "ja"
    kn = "kn"
    ko = "ko"
    kz = "kz"
    mn = "mn"
    lt = "lt"
    lv = "lv"
    nl = "nl"
    no = "no"
    pl = "pl"
    pt = "pt"
    pt_BR = "pt_BR"
    ro = "ro"
    ru = "ru"
    sl = "sl"
    sk = "sk"
    sr = "sr"
    sv = "sv"
    te = "te"
    tet = "tet"
    tg = "tg"
    tr = "tr"
    th = "th"
    uk = "uk"
    vi = "vi"
    zh = "zh"
    zh_CN = "zh_CN"
    zh_TW = "zh_TW"
    zh_HK = "zh_HK"

    @property
    def label(self) -> str:
        """Returns the human-readable label for the language."""
        SUPPORTED_LANGUAGES: dict[str, str] = {
            "en": "English",
            "am": "Amharic",
            "ar": "Arabic",
            "az": "Azerbaijani",
            "be": "Belarusian",
            "bn": "Bangladeshi",
            "ca": "Catalan",
            "ce": "Chechen",
            "cs": "Czech",
            "cy": "Welsh",
            "da": "Danish",
            "de": "German",
            "en_GB": "English - Great Britain",
            "en_IN": "English - India",
            "en_NG": "English - Nigeria",
            "es": "Spanish",
            "es_CO": "Spanish - Colombia",
            "es_CR": "Spanish - Costa Rica",
            "es_GT": "Spanish - Guatemala",
            "es_VE": "Spanish - Venezuela",
            "eu": "EURO",
            "fa": "Farsi",
            "fi": "Finnish",
            "fr": "French",
            "fr_BE": "French - Belgium",
            "fr_CH": "French - Switzerland",
            "fr_DZ": "French - Algeria",
            "he": "Hebrew",
            "hi": "Hindi",
            "hu": "Hungarian",
            "hy": "Armenian",
            "id": "Indonesian",
            "is": "Icelandic",
            "it": "Italian",
            "ja": "Japanese",
            "kn": "Kannada",
            "ko": "Korean",
            "kz": "Kazakh",
            "mn": "Mongolian",
            "lt": "Lithuanian",
            "lv": "Latvian",
            "nl": "Dutch",
            "no": "Norwegian",
            "pl": "Polish",
            "pt": "Portuguese",
            "pt_BR": "Portuguese - Brazilian",
            "ro": "Romanian",
            "ru": "Russian",
            "sl": "Slovene",
            "sk": "Slovak",
            "sr": "Serbian",
            "sv": "Swedish",
            "te": "Telugu",
            "tet": "Tetum",
            "tg": "Tajik",
            "tr": "Turkish",
            "th": "Thai",
            "uk": "Ukrainian",
            "vi": "Vietnamese",
            "zh": "Chinese - Traditional",
            "zh_CN": "Chinese - Simplified / Mainland China",
            "zh_TW": "Chinese - Traditional / Taiwan",
            "zh_HK": "Chinese - Traditional / Hong Kong",
        }
        return SUPPORTED_LANGUAGES.get(self, self.name)


class NumToWordsRule(TransformationRule):
    """
    Transformation rule that converts numeric values to their word representation.
    """

    type: Literal["num_to_words"] = "num_to_words"
    lang: NumToWordsLanguages = Field(
        default=NumToWordsLanguages.ru,
        title="Language",
        description="Language for number-to-words conversion.",
    )

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: NumToWordsLanguages) -> NumToWordsLanguages:
        if v not in NumToWordsLanguages:
            raise ValueError(f"Unsupported language '{v}' for num2words rule.")
        return v

    @override
    def default_var_rename(self, old_var_name: str) -> str:
        return f"{old_var_name}_in_words"

    @override
    def default_header_rename(self, old_header_name: str) -> str:
        return f"{old_header_name} (in words)"

    @override
    @classmethod
    def get_rule_name(cls) -> str:
        return "Number to Words"

    @override
    def transform(self, value: str) -> str:
        """
        Transforms a numeric string into its word representation.

        Args:
            value (str): The numeric string to convert.

        Returns:
            str: The word representation of the number.
        """
        if not value:
            raise ValueError("Input value for NumToWordsRule cannot be empty.")

        try:
            words = num2words.num2words(value, lang=self.lang.value)
            return words
        except Exception as e:
            raise ValueError(
                f"Failed to convert value '{value}' to words in language '{self.lang.value} - {self.lang.label}': {e}"
            )
