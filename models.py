from enum import Enum
from typing import Any, Optional, List

# your “typo → canonical” map
_POWER_ALIASES = {
    "EGMANY": "GERMANY",
    "GERMAN": "GERMANY",
    "UK": "ENGLAND",
    "BRIT": "ENGLAND",
    "Germany": "GERMANY",
    "England": "ENGLAND",
    "France": "FRANCE",
    "Italy": "ITALY",
    "Russia": "RUSSIA",
    "Austria": "AUSTRIA",
    "Turkey": "TURKEY",
    # 3-letter codes
    "AUT": "AUSTRIA",
    "AUS": "AUSTRIA",
    "ENG": "ENGLAND",
    "FRA": "FRANCE",
    "GER": "GERMANY",
    "ITA": "ITALY",
    "RUS": "RUSSIA",
    "TUR": "TURKEY",
}

POWERS_ORDER: List[str] = [
    "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY",
    "ITALY", "RUSSIA", "TURKEY",
]

class PowerEnum(str, Enum):
    AUSTRIA = "AUSTRIA"
    ENGLAND = "ENGLAND"
    FRANCE = "FRANCE"
    GERMANY = "GERMANY"
    ITALY = "ITALY"
    RUSSIA = "RUSSIA"
    TURKEY = "TURKEY"

    @classmethod
    def _missing_(cls, value: Any) -> Optional["Enum"]:
        """
        Called when you do PowerEnum(value) and `value` isn't one of the raw enum values.
        Here we normalize strings to upper‐stripped, apply aliases, then retry.
        """
        if isinstance(value, str):
            normalized = value.upper().strip()
            # apply any synonyms/typos
            normalized = _POWER_ALIASES.get(normalized, normalized)
            # look up in the normal value→member map
            member = cls._value2member_map_.get(normalized)
            if member is not None:
                return member

        # by default, let Enum raise the ValueError
        return super()._missing_(value)
