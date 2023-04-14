from typing import Final
from enum import Enum

class ToggledBlockType(Enum):
    if_ = "if"
    else_ = "else"
    elif_ = "elif"


# TODO: make configurable to allow for other user specific jinja configurations
NON_EXISTING_STR: Final[str] = "____THIS_DOESN'T_EXIST____"

# indentetion defaults
DEFAULT_MAPPING_INDENT: Final[int] = 2
DEFAULT_SEQUENCE_INDENT: Final[int] = 2
DEFAULT_OFFSET_INDENT: Final[int] = 0
# yaml tags
YAML_MAP_TAG: Final[str] = "tag:yaml.org,2002:map"
YAML_SEQ_TAG: Final[str] = "tag:yaml.org,2002:seq"
# conditional comment templates
IF_TEMPLATE: Final[str] = '{{% if defines.get("{}") %}}'
ELIF_TEMPLATE: Final[str] = '{{% elif defines.get("{}") %}}'
IF_NOT_TEMPLATE: Final[str] = '{{% if not defines.get("{}") %}}'
ELIF_NOT_TEMPLATE: Final[str] = '{{% elif not defines.get("{}") %}}'
ELSE_COMMENT: Final[str] = "{% else %}"
ENDIF_COMMENT: Final[str] = "{% endif %}"

# toggled structure key constants
TOGGLE_KEY_PREFIX: Final[str] = "__toggled__"
UNIQUE_TOGGLE_CNT: int = 0
# toggled structure tag constants
TOGGLE_TAG_PREFIX: Final[str] = "!toggled_"
TYPE_SEP: Final[str] = "@"
TOGGLE_SEP: Final[str] = "&"
TOGGLE_VALUE_SETTER: Final[str] = "="
# toggled key deduplication
DEDUPLICATOR: Final[str] = "__deduplicator__"
UNIQUE_CNT: int = 0
CONSTRUCTOR_CNT: int = 0