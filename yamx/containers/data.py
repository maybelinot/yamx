from dataclasses import dataclass, replace
from typing import Any, ClassVar, Optional, Tuple, Union

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.tag import Tag

from yamx.constants import (
    CONDITIONAL_TAG,
    DEDUPLICATOR_UPD,
    YAML_MAP_TAG,
    YAML_SEQ_TAG,
    ConditionalBlockType,
)

CONDITIONAL_UPD_COUNTER: int = 0


@dataclass(frozen=True)
class Condition:
    raw_value: str


@dataclass(frozen=True)
class CmpValue:
    value: Any

    def __lt__(self, other) -> bool:
        if isinstance(other, ConditionalGroup):
            return True
        else:
            return self.value < other.value


@dataclass(frozen=True)
class ConditionalData:
    """Wrapper for loaded data"""

    _data: Any

    @property
    def data(self) -> Any:
        return self._data

    def __getitem__(self, key) -> Any:
        # TODO: assign method when ConditionalData is created dynamically
        if isinstance(self._data, ConditionalMap):
            return _get_from_conditional_map(self._data, key)

        raise NotImplementedError()

    def __setitem__(self, key, value) -> None:
        if isinstance(value, ConditionalSelectionGroup):
            global CONDITIONAL_UPD_COUNTER
            dummy_block_key = f"{DEDUPLICATOR_UPD}{CONDITIONAL_UPD_COUNTER}"
            self._data[dummy_block_key] = value.to_conditional_group(key)
        else:
            self._data[key] = value


class ConditionalMap(CommentedMap):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        tag = Tag(suffix=YAML_MAP_TAG)
        self.yaml_set_ctag(tag)


class ConditionalSeq(CommentedSeq):
    def __init__(self, *args, **kw) -> None:
        tag = Tag(suffix=YAML_SEQ_TAG)
        self.yaml_set_ctag(tag)
        super().__init__(*args, **kw)


@dataclass(frozen=True)
class ConditionalBlock:
    yaml_tag: ClassVar[str] = CONDITIONAL_TAG

    data: Any
    typ: ConditionalBlockType
    condition: Optional[Condition]

    @classmethod
    def to_yaml(cls, _, __):
        raise NotImplementedError(f"{cls.__name__} should never be dumped to yaml.")

    @classmethod
    def from_yaml(cls, constructor, node):
        data = CommentedMap()
        constructor.construct_mapping(node, data, deep=True)
        data["typ"] = ConditionalBlockType(data["typ"])
        data["condition"] = Condition(data["condition"])

        return cls(**data)


@dataclass(frozen=True)
class ConditionalSelectionGroup:
    condition: Optional[Condition]
    # TODO: introduce type of conditional group/ subclassing
    # TODO: support scalars
    body: Any
    # elif_bodies is None to identify elif nodes that have only body filled
    elif_bodies: Tuple["ConditionalSelectionGroup", ...] = tuple()
    else_body: Any = None

    def to_conditional_group(self, key: str) -> "ConditionalGroup":
        elif_bodies = tuple(
            ConditionalGroup(
                body=ConditionalMap({key: elif_body.body}),
                condition=elif_body.condition,
            )
            for elif_body in self.elif_bodies
        )
        return ConditionalGroup(
            condition=self.condition,
            body=ConditionalMap({key: self.body}),
            elif_bodies=elif_bodies,
            else_body=self.else_body and ConditionalMap({key: self.else_body}),
        )


@dataclass(frozen=True)
class ConditionalGroup:
    condition: Optional[Condition]
    # TODO: introduce type of conditional group/ subclassing
    # TODO: support scalars
    body: Union[ConditionalMap, ConditionalSeq]
    # elif_bodies is None to identify elif nodes that have only body filled
    elif_bodies: Tuple["ConditionalGroup", ...] = tuple()
    else_body: Optional[Union[ConditionalMap, ConditionalSeq]] = None

    def __lt__(self, other) -> bool:
        # compare by condition string
        if isinstance(other, ConditionalGroup):
            # we compare only "if" ConditionalGroup, not "else" (where condition can be empty)
            assert self.condition is not None and other.condition is not None
            return self.condition.raw_value < other.condition.raw_value
        else:
            return False

    def with_conditional_block(
        self,
        data: Union[ConditionalMap, ConditionalSeq],
        typ: ConditionalBlockType,
        condition: Optional[Condition],
    ) -> "ConditionalGroup":
        """Extends conditional group with new elif/else conditional blocks"""
        if typ is ConditionalBlockType.elif_:
            assert isinstance(self.elif_bodies, tuple)
            elif_groups = self.elif_bodies + (
                ConditionalGroup(body=data, condition=condition),
            )
            return replace(self, elif_bodies=elif_groups)
        elif typ is ConditionalBlockType.else_:
            assert (
                self.else_body is None
            ), f"Cannot set else_body to {self}, else_body is not empty."
            return replace(self, else_body=data)
        else:
            raise ValueError(f"Unexpected conditional element of type {typ}")

    def __iter__(self):
        """custom iterator: captures all keys from conditional blocks as well"""
        keys_set = set(self.body.keys())
        for elif_block in self.elif_bodies:
            keys_set.update(elif_block.keys())
        if self.else_body:
            keys_set.update(self.else_body.keys())

        return iter(keys_set)

    def __contains__(self, key: str) -> bool:
        return key in iter(self)

    def __getitem__(self, key: str) -> ConditionalSelectionGroup:
        if key not in self:
            raise KeyError(f'Key "{key}" was not found in conditional block')

        def _get_from_body(body: ConditionalMap) -> CommentedMap:
            return None if key not in body else body[key]

        body = _get_from_body(self.body)
        elif_bodies = tuple(
            ConditionalSelectionGroup(
                body=_get_from_body(elif_body.body),
                condition=elif_body.condition,
            )
            for elif_body in self.elif_bodies
        )
        else_body = self.else_body and _get_from_body(self.else_body)
        return ConditionalSelectionGroup(
            # TODO: copy annotation from previous key-map
            # TODO: support empty conditions
            body=body,
            elif_bodies=elif_bodies,
            else_body=else_body,
            condition=self.condition,
        )


def _get_from_conditional_map(data: ConditionalMap, key: str) -> Any:
    res = None
    for data_key, value in data.items():
        if not isinstance(value, ConditionalGroup):
            if not data_key == key:
                continue
            res = value
            # TODO: move to validation of data structures?
            # continue to validate for duplication
            continue
        # TODO: support key in value.keys()
        try:
            key_value = value[key]
        except KeyError:
            continue
        if res is not None:
            raise Exception("duplicate field in different conditional blocks found")

        res = key_value

    return res
