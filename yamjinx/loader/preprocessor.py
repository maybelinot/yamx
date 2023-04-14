import io
from typing import List, Optional, Tuple, Union

from jinja2 import nodes
from jinja2.sandbox import SandboxedEnvironment
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yamjinx.constants import (
    NON_EXISTING_STR,
    TOGGLE_KEY_PREFIX,
    TOGGLE_SEP,
    TOGGLE_TAG_PREFIX,
    TOGGLE_VALUE_SETTER,
    TYPE_SEP,
    ToggledBlockType,
)

UNIQUE_TOGGLE_CNT: int = 0

yaml = YAML()


def translate_config_flags(data: str) -> str:
    """Translates config flags defined with jinja syntax into yaml-compatible configuration.
    This step is required to create common interface which can be loaded and dumped as a
    single operation, without any information loss.

    All Toggled dict/list values are moved under unique `__toggled__\\d` key, which is tagged
    with toggle info in a format of:
        '!toggled_{toggle1_key}={toggle1_val}&{toggle2_key}={toggle2_val}'
    That way deduplication of Toggled fields is ensured for mappings.

    Example input:

        '''
        dictionary:
          flag1: value1
          # {% if defines.get('toggle') %}
          flag2: value2
          # {% else %}
          flag2: value3
          # {% endif %}
        list:
        - value1
        # {% if defines.get('toggle') %}
        - value2
        # {% else %}
        - value3
        # {% endif %}
        '''

    Example output:
        '''
        dictionary:
          flag1: value1
          __toggled__0: !toggled_IS_LOCAL=true
            flag2: value2
          __toggled__1: !toggled_IS_LOCAL=false
            flag2: value3
        list:
        - value1
        - !toggled_IS_LOCAL=true
          __toggled__2:
          - value2
        - !toggled_IS_LOCAL=false
          __toggled__3:
          - value3
        '''

    """
    env = SandboxedEnvironment(
        # variable parsing is disabled this way
        variable_start_string=NON_EXISTING_STR,
        variable_end_string=NON_EXISTING_STR,
        # yaml parsing relies on this configuration
        trim_blocks=True,
    )
    # resetting filters and globals to limit its usage
    env.filters = {}
    env.globals = {}

    jinja_ast = env.parse(data)
    jinja_yaml_ast = parse_jinja(jinja_ast)

    return jinja_yaml_ast


def parse_jinja(
    jinja_ast: Union[nodes.Template, nodes.Output, nodes.If, nodes.TemplateData]
) -> str:
    # root node of jinja - just process internals
    if isinstance(jinja_ast, nodes.Template):
        processed = "".join(map(parse_jinja, jinja_ast.body))
    # intermediate node which contain conditions and plain text
    elif isinstance(jinja_ast, nodes.Output):
        processed = "".join(map(parse_jinja, jinja_ast.nodes))
    # Toggled node
    elif isinstance(jinja_ast, nodes.If):
        processed = _process_jinja_if_node(jinja_ast)
    # simple text node - no conditions are expected inside
    elif isinstance(jinja_ast, nodes.TemplateData):
        processed = _remove_suffix(jinja_ast.data).rstrip(" ")
    else:
        raise TypeError(f"Unexpected jinja ast node of type {type(jinja_ast)}.")

    return processed


# _remove_suffix to remove any jinja syntax comments leftovers (let's hope it will not kick us back)
# NOTE: only works when jinja blocks defined with a space between `#` and a block
def _remove_suffix(s: str, suffix="# ") -> str:
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def _process_jinja_if_node(
    jinja_ast: nodes.If, typ: Optional[ToggledBlockType] = None
) -> str:
    toggle_name, toggle_value = _extract_toggle_from_if_node(jinja_ast)
    if_data = "".join(map(parse_jinja, jinja_ast.body))

    if_processed = process_conditions(
        if_data,
        typ=typ or ToggledBlockType.if_,
        conds=[(toggle_name, str(toggle_value))],
    )

    elif_processed = [
        _process_jinja_if_node(elif_node, typ=ToggledBlockType.elif_)
        for elif_node in jinja_ast.elif_
    ]

    else_data = "".join(map(parse_jinja, jinja_ast.else_))
    else_processed = process_conditions(else_data, typ=ToggledBlockType.else_)

    # filter out empty strings
    processed_nodes = filter(None, [if_processed, *elif_processed, else_processed])
    return "\n".join(processed_nodes) + "\n"


def _extract_toggle_from_if_node(if_node) -> Tuple[str, bool]:
    # we have negation in condition
    if isinstance(if_node.test, nodes.Not):
        return if_node.test.node.args[0].value, False
    return if_node.test.args[0].value, True


def process_conditions(
    data: str, typ: ToggledBlockType, conds: List[Tuple[str, str]] = []
) -> str:
    """
    # here we rely on the fact that yaml structure is valid and we can:
    # * load it with YAML loader
    # * set dynamically generated tags based on conditions
    # * dump it back to string form
    """
    global UNIQUE_TOGGLE_CNT
    yaml_data = yaml.load(data)

    # in case
    if yaml_data is None:
        return data

    # TODO: cover \t and other whitespaces
    leading_spaces = len(data.lstrip("\n")) - len(data.lstrip("\n").lstrip(" "))

    toggles_str = TOGGLE_SEP.join([TOGGLE_VALUE_SETTER.join(cond) for cond in conds])
    tag = f"{TOGGLE_TAG_PREFIX}{typ.value}{TYPE_SEP}{toggles_str}"
    key = f"{TOGGLE_KEY_PREFIX}{UNIQUE_TOGGLE_CNT}"
    if isinstance(yaml_data, CommentedMap):
        # abstraction level has to be created in order to encapsulate toggled fields
        # TODO: check that tags aren't used before on that map object
        yaml_data.yaml_set_tag(tag)
        res_yaml_data = CommentedMap({key: yaml_data})
    elif isinstance(yaml_data, CommentedSeq):
        # similar structure is created for list fields
        map_data = CommentedMap({key: yaml_data})
        map_data.yaml_set_tag(tag)
        res_yaml_data = [map_data]
    else:
        # TODO: support simple scalars
        raise NotImplementedError
    UNIQUE_TOGGLE_CNT += 1

    string_stream = io.StringIO()
    yaml.dump(res_yaml_data, stream=string_stream)
    res = string_stream.getvalue()
    string_stream.close()
    space_indent = " " * leading_spaces
    # add indentation in the beginning of each line
    res = res.replace("\n", f"\n{space_indent}")
    # add indentation in the beginning
    return f"{space_indent}{res}".rstrip()
