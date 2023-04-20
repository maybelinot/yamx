import io
from typing import Dict, List, Optional, Union

from jinja2 import nodes
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yamjinx.constants import CONDITIONAL_TAG, TOGGLE_KEY_PREFIX, ToggledBlockType
from yamjinx.loader.condition import extract_condition
from yamjinx.loader.utils import get_jinja_env

UNIQUE_TOGGLE_CNT: int = 0

yaml = YAML()
JINJA_ENV = get_jinja_env()


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
          __toggled__0: !conditional
            data:
                flag2: value2
            typ: if
            condition: defines.get('toggle')
          __toggled__1: !conditional
            data:
                flag2: value3
            typ: else
            condition: null
        list:
        - value1
        - __toggled__2: !conditional
            data:
            - value2
            typ: if
            condition: defines.get('toggle')
        - __toggled__3: !conditional
            data:
            - value3
            typ: else
            condition: null
        '''

    """

    jinja_ast = JINJA_ENV.parse(data)
    jinja_yaml_ast = _parse_jinja(jinja_ast)

    return jinja_yaml_ast


def _parse_jinja(
    jinja_ast: Union[nodes.Template, nodes.Output, nodes.If, nodes.TemplateData]
) -> str:
    # root node of jinja - just process internals
    if isinstance(jinja_ast, nodes.Template):
        processed = "".join(map(_parse_jinja, jinja_ast.body))
    # intermediate node which contain conditions and plain text
    elif isinstance(jinja_ast, nodes.Output):
        processed = "".join(map(_parse_jinja, jinja_ast.nodes))
    # Toggled node
    elif isinstance(jinja_ast, nodes.If):
        processed = _process_jinja_if_node(jinja_ast, typ=ToggledBlockType.if_)
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


def _process_jinja_if_node(jinja_ast: nodes.If, typ: ToggledBlockType) -> str:
    if_data = "".join(map(_parse_jinja, jinja_ast.body))
    raw_condition = extract_condition(jinja_ast.test, JINJA_ENV)

    if_processed = _process_conditions(
        if_data,
        typ=typ,
        condition=raw_condition,
    )

    elif_processed = [
        _process_jinja_if_node(elif_node, typ=ToggledBlockType.elif_)
        for elif_node in jinja_ast.elif_
    ]

    else_data = "".join(map(_parse_jinja, jinja_ast.else_))
    else_processed = _process_conditions(else_data, typ=ToggledBlockType.else_)

    # filter out empty strings
    processed_nodes = filter(None, [if_processed, *elif_processed, else_processed])
    return "\n".join(processed_nodes) + ("" if typ is ToggledBlockType.elif_ else "\n")


def _process_conditions(
    raw_data: str, typ: ToggledBlockType, condition: Optional[str] = None
) -> str:
    """
    # here we rely on the fact that yaml structure is valid and we can:
    # * load it with YAML loader
    # * set dynamically generated tags based on conditions
    # * dump it back to string form
    """
    global UNIQUE_TOGGLE_CNT
    yaml_data = yaml.load(raw_data)

    # in case
    if yaml_data is None:
        return raw_data

    # TODO: cover \t and other whitespaces
    leading_spaces = len(raw_data.lstrip("\n")) - len(raw_data.lstrip("\n").lstrip(" "))

    data = CommentedMap(
        {
            "data": yaml_data,
            "typ": typ.value,
            "condition": condition,
        }
    )
    data.yaml_set_tag(CONDITIONAL_TAG)

    res_yaml_data: Union[Dict[str, CommentedMap], List[CommentedMap]]
    if isinstance(yaml_data, CommentedMap):
        # create unique key to separate conditional block from other fields
        key = f"{TOGGLE_KEY_PREFIX}{UNIQUE_TOGGLE_CNT}"
        UNIQUE_TOGGLE_CNT += 1
        # abstraction level has to be created in order to encapsulate toggled fields
        res_yaml_data = {key: data}
    elif isinstance(yaml_data, CommentedSeq):
        # similar structure is created for list fields
        res_yaml_data = [data]
    else:
        # TODO: support simple scalars
        raise NotImplementedError(
            f"Conditions on {type(yaml_data)} are not supported yet. :("
        )

    string_stream = io.StringIO()
    yaml.dump(res_yaml_data, stream=string_stream)
    res = string_stream.getvalue()
    string_stream.close()
    space_indent = " " * leading_spaces
    # add indentation in the beginning of each line
    res = res.replace("\n", f"\n{space_indent}")
    # add indentation in the beginning
    return f"{space_indent}{res}".rstrip()
