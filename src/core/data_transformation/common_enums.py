from enum import Enum


class PytrovichLanguages(Enum):
    RUSSIAN = "ru"

    @property
    def label(self) -> str:
        """Returns the human-readable label for the language."""
        SUPPORTED_LANGUAGES: dict[PytrovichLanguages, str] = {
            PytrovichLanguages.RUSSIAN: "Russian"
        }
        return SUPPORTED_LANGUAGES.get(self, self.name)
