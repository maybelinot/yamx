import io

import pytest

from yamx import YAMX
from yamx.extra import extract_toggles


@pytest.mark.parametrize(
    "raw_config, expected_toggles",
    [
        ("", []),
        # list toggles
        (
            """
- []
# {% if defines.get("toggle_a") %}
- value2
- value3
# {% endif %}""",
            ["toggle_a"],
        ),
        # root level toggle
        (
            """
field: []
# {% if defines.get("toggle_a") %}
field2: value2
field3: value3
# {% endif %}""",
            ["toggle_a"],
        ),
        # toggle deep in the structure
        (
            """
mapping:
  field: []
  # {% if defines.get("toggle_a") %}
  field2: value2
  field3: value3
  # {% else %}
  field2: []
  field3: []
  # {% endif %}""",
            ["toggle_a"],
        ),
        # many toggles
        (
            """
mapping:
  field: []
  # {% if defines.get("toggle_a") %}
  field2: value2
  field3: value3
  # {% endif %}
list:
# {% if defines.get("toggle_b") %}
- 1
# {% else %}
- 2
# {% endif %}""",
            ["toggle_a", "toggle_b"],
        ),
        # elif toggles
        (
            """
mapping:
  field: []
  # {% if defines.get("toggle_a") %}
  field2: value2
  # {% elif defines.get("toggle_b") %}
  field3: value3
  # {% endif %}
list:
# {% if defines.get("toggle_c") %}
- 1
# {% elif defines.get("toggle_d") %}
- 2
# {% endif %}""",
            ["toggle_a", "toggle_b", "toggle_c", "toggle_d"],
        ),
    ],
)
def test_toggle_extraction(raw_config, expected_toggles):
    # remove leading newline

    raw_config = raw_config.lstrip("\n")
    cyaml = YAMX(sort_keys=False)

    with io.StringIO(raw_config) as input_stream:
        data = cyaml.load(input_stream)

    assert extract_toggles(data.data) == set(expected_toggles)
