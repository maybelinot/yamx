import io

import pytest
from ruamel.yaml import YAML

from yamx import YAMX
from yamx.extra import ResolvingContext, extract_toggles, resolve_toggles


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
        # toggles.get
        (
            """
# {% if toggles.get("toggle_a") %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
        #         # toggles[]
        (
            """
# {% if toggles["toggle_a"] %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
        # toggles.
        (
            """
# {% if toggles.toggle_a %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
        # config_flags.get
        (
            """
# {% if config_flags.get("toggle_a") %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
        # config_flags[]
        (
            """
# {% if config_flags["toggle_a"] %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
        # config_flags.
        (
            """
# {% if config_flags.toggle_a %}
field: value
# {% endif %}""",
            ["toggle_a"],
        ),
    ],
)
def test_toggle_extraction(raw_config, expected_toggles):
    cyaml = YAMX(sort_keys=False)

    with io.StringIO(raw_config) as input_stream:
        data = cyaml.load(input_stream)

    assert extract_toggles(data) == set(expected_toggles)


def test_toggle_extraction_fail():
    cyaml = YAMX(sort_keys=False)
    raw_config = """
{% if not_toggles.get("toggle_a") %}
field: value
{% endif %}"""

    with io.StringIO(raw_config) as input_stream:
        data = cyaml.load(input_stream)
    with pytest.raises(
        Exception, match=r'Unsupported toggle condition: not_toggles.get\("toggle_a"\)'
    ):
        extract_toggles(data)


@pytest.mark.parametrize(
    "raw_config, expected",
    [
        # no conditions
        (
            """
active: false
params: 1
""",
            """
active: false
params: 1
""",
        ),
        # toggled
        (
            """
active: false
{% if defines.get("toggle_a") %}
params: 1
{% else %}
params: 2
{% endif %}
""",
            """
active: false
params: 1
""",
        ),
        # contextual elif conditions
        (
            """
active: false
{% if not defines.get("toggle_a") %}
params: 1
{% elif defines.get("toggle_a") %}
params: 2
{% else %}
params: 3
{% endif %}
""",
            """
active: false
params: 2
""",
        ),
        # nested conditions map
        (
            """
active: false
{% if defines.get("toggle_a") %}
map:
  val: 1
  {% if defines.get("toggle_b") %}
  params: 3
  {% else %}
  params: 2
  {% endif %}
  val2: 2
{% endif %}
""",
            """
active: false
map:
  val: 1
  params: 2
  val2: 2
""",
        ),
        # conditions seq
        (
            """
list:
{% if defines.get("toggle_a") %}
- 1
{% endif %}
- 2
""",
            """
list:
- 1
- 2
""",
        ),
        # nested conditions seq
        (
            """
active: false
{% if defines.get("toggle_b") %}
params: 1
{% else %}
list:
- key: val
{% if defines.get("toggle_a") %}
- key: val1
{% endif %}
- key: val2
{% endif %}
""",
            """
active: false
list:
- key: val
- key: val1
- key: val2
""",
        ),
        # getitem
        (
            """
# {% if defines["toggle_a"] %}
field: value
# {% endif %}""",
            "field: value",
        ),
        # context attr
        (
            """
# {% if defines.toggle_a %}
field: value
# {% endif %}""",
            "field: value",
        ),
        # single field
        (
            """
map:
    # {% if defines.toggle_b %}
    field: value
    # {% endif %}""",
            "map: {}",
        ),
        # single item
        (
            """
list:
    # {% if defines.toggle_b %}
    - value
    # {% endif %}""",
            "list: []",
        ),
    ],
)
def test_resolve_toggles(raw_config, expected):
    yamx = YAMX()
    context = {"defines": ResolvingContext({"toggle_a": True, "toggle_b": False})}

    conditional_data = yamx.load_from_string(raw_config)
    resolved_data = resolve_toggles(conditional_data, context)
    yaml = YAML(typ=["string"])
    resolved_str = yaml.dump_to_string(resolved_data)
    assert resolved_str == expected.strip()


@pytest.mark.parametrize(
    "raw_config",
    [
        """
{% if defines.get("toggle_a") and defines.get("toggle_b") %}
a: 1
{% endif %}
""",
        """
{% if context.get("toggle_a") %}
a: 1
{% endif %}
""",
    ],
)
def test_resolve_failed(raw_config):
    yamx = YAMX()
    data = yamx.load_from_string(raw_config)
    context = ResolvingContext({"defines": {"toggle_a": True}})
    with pytest.raises(Exception, match="Unsupported toggle condition: "):
        resolve_toggles(data, context)
