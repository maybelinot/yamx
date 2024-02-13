from enum import Enum
from typing import Final


class ConditionalBlockType(Enum):
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
IF_CONDITION_TEMPLATE: Final[str] = "{{% if {} %}}"
ELIF_CONDITION_TEMPLATE: Final[str] = "{{% elif {} %}}"
ELSE_COMMENT: Final[str] = "{% else %}"
ENDIF_COMMENT: Final[str] = "{% endif %}"

# conditional structure key constants
CONDITIONAL_KEY_PREFIX: Final[str] = "__condition__"

# conditional structure tag constants
CONDITIONAL_TAG: Final[str] = "conditional"

# conditional key deduplication
DEDUPLICATOR: Final[str] = "__dedup__"
DEDUPLICATOR_UPD: Final[str] = "__dedup_upd__"
