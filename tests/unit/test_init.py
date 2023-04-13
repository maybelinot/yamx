import pytest
from ruamel.yaml import YAML

from yamjinx import YAMJinX


def test_default():
    YAMJinX()


def test_custom_yaml():
    _ = YAMJinX(yaml=YAML(typ=["rt", "string"]))


def test_missing_rt_constructor():
    with pytest.raises(
        AssertionError, match="RoundTripLoader/RoundTripDumper is required"
    ):
        _ = YAMJinX(yaml=YAML(typ=["string"]))
