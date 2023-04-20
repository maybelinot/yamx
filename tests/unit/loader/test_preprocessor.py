from unittest.mock import patch

import pytest

from yamjinx.loader.preprocessor import translate_config_flags


@pytest.mark.parametrize(
    "raw_data,translated_data",
    [
        # simple map
        (
            """
{% if condition %}
a: 1
{% endif %}
""",
            """
__condition__0: !conditional
  data:
    a: 1
  typ: if
  condition: condition
""",
        ),
        # complex map
        (
            """
{% if condition1 %}
a: 1
{% elif condition2 %}
a: 2
{% elif condition3 %}
a: 3
{% else %}
a: 4
{% endif %}
""",
            """
__condition__0: !conditional
  data:
    a: 1
  typ: if
  condition: condition1
__condition__1: !conditional
  data:
    a: 2
  typ: elif
  condition: condition2
__condition__2: !conditional
  data:
    a: 3
  typ: elif
  condition: condition3
__condition__3: !conditional
  data:
    a: 4
  typ: else
  condition:
""",
        ),
        # simple list
        (
            """
{% if condition %}
- 1
{% endif %}
""",
            """
- !conditional
  data:
  - 1
  typ: if
  condition: condition
""",
        ),
        # complex list
        (
            """
{% if condition1 %}
- 1
{% elif condition2 %}
- 2
{% elif condition3 %}
- 3
{% else %}
- 4
{% endif %}
""",
            """
- !conditional
  data:
  - 1
  typ: if
  condition: condition1
- !conditional
  data:
  - 2
  typ: elif
  condition: condition2
- !conditional
  data:
  - 3
  typ: elif
  condition: condition3
- !conditional
  data:
  - 4
  typ: else
  condition:
""",
        ),
    ],
)
@patch("yamjinx.loader.preprocessor.UNIQUE_CONDITION_CNT", 0)
def test_translate_config_flags(raw_data, translated_data):
    assert translate_config_flags(raw_data) == translated_data
