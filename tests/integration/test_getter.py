import io

import pytest

from yamx import YAMX
from yamx.containers.data import ConditionalData, ConditionalMap


@pytest.mark.parametrize(
    "original,selection,expected",
    [
        (
            {},
            """
field: 1
{% if True %}
field2: 1
field3: 3
{% else %}
field2: 2
{% endif %}
""",
            """
# {% if True %}
field3: 1
# {% else %}
field3: 2
# {% endif %}""",
        ),
        (
            {"field": 0},
            """
field: 1
{% if True %}
field2: 1
field3: 3
{% else %}
field2: 2
{% endif %}
""",
            """
field: 0
# {% if True %}
field3: 1
# {% else %}
field3: 2
# {% endif %}""",
        ),
    ],
)
def test_map_update_with_selection(original, selection, expected):
    res_data = ConditionalData(ConditionalMap(original))

    yamx = YAMX()
    with io.StringIO(selection.lstrip("\n")) as input_stream:
        data = yamx.load(input_stream)

    res_data["field3"] = data["field2"]

    res = yamx.dump_to_string(res_data)
    assert res == expected.lstrip()
