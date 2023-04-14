from typing import Any

from yamjinx.constants import (
    DEDUPLICATOR,
    NON_EXISTING_STR,
    TOGGLE_KEY_PREFIX,
    TOGGLE_TAG_PREFIX,
)


def validate_content(data: Any) -> None:
    """Checks that internally used fields do not exist in input yaml file"""
    assert all(
        value not in data
        for value in (
            TOGGLE_KEY_PREFIX,
            NON_EXISTING_STR,
            DEDUPLICATOR,
            TOGGLE_TAG_PREFIX,
        )
    )
