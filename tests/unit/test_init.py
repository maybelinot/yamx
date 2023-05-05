import pytest
from ruamel.yaml import YAML

from yamx import YAMX


def test_default():
    YAMX()


def test_custom_yaml():
    YAMX(yaml=YAML(typ=["rt", "string"]))


def test_missing_rt_constructor():
    with pytest.raises(
        AssertionError, match="RoundTripLoader/RoundTripDumper is required"
    ):
        YAMX(yaml=YAML(typ=["string"]))
