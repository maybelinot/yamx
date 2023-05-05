from typing import Any

from yamx.constants import (
    CONDITIONAL_KEY_PREFIX,
    CONDITIONAL_TAG,
    DEDUPLICATOR,
    DEDUPLICATOR_UPD,
    NON_EXISTING_STR,
)


def validate_content(data: Any) -> None:
    """Checks that internally used fields do not exist in input yaml file"""
    assert all(
        value not in data
        for value in (
            CONDITIONAL_KEY_PREFIX,
            NON_EXISTING_STR,
            DEDUPLICATOR,
            DEDUPLICATOR_UPD,
            CONDITIONAL_TAG,
        )
    )
