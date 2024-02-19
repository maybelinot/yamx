import pytest

from yamx.utils import strtobool


@pytest.mark.parametrize(
    "value_to_test, expected",
    [
        ("y", 1),
        ("yes", 1),
        ("YeS", 1),
        ("True", 1),
        ("t", 1),
        ("1", 1),
        ("oN", 1),
        ("false", 0),
        ("off", 0),
        ("f", 0),
        ("n", 0),
        ("NO", 0),
        ("0", 0),
    ],
)
def test_strtobool_positive(value_to_test: str, expected: int):
    actual = strtobool(value_to_test)
    assert actual == expected


@pytest.mark.parametrize(
    "invalid_value",
    [
        " 1",
        "11",
        "no ",
        "hello",
        "!",
        "",
        "00",
        "*",
        ".",
    ],
)
def test_strtobool_negative(invalid_value: str):
    with pytest.raises(ValueError, match="invalid truth value"):
        strtobool(invalid_value)
