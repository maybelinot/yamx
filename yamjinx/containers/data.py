from typing import Any, Mapping, Optional, Tuple, Union

from attr import evolve, frozen
from immutables import Map
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yamjinx.constants import ToggledBlockType


@frozen
class CmpValue:
    value: Any

    def __lt__(self, other) -> bool:
        if isinstance(other, ToggledGroup):
            return True
        else:
            return self.value < other.value


class ToggledMap(CommentedMap):
    def __init__(
        self,
        typ: Optional[ToggledBlockType] = None,
        toggles: Optional[Mapping[str, bool]] = None,
    ):
        super().__init__()
        self.yaml_set_tag("tag:yaml.org,2002:map")
        self._typ = typ
        self._toggles = toggles or Map()


class ToggledSeq(CommentedSeq):
    def __init__(self) -> None:
        self.yaml_set_tag("tag:yaml.org,2002:seq")
        super().__init__()


@frozen
class ToggledGroup:
    # TODO: support scalars
    body: Union[ToggledMap, ToggledSeq]
    toggles_: Mapping[str, bool]
    # elif_bodies is None to identify elif nodes that have only body filled
    elif_bodies: Optional[Tuple[Union[ToggledMap, ToggledSeq], ...]] = tuple()
    else_body: Optional[Union[ToggledMap, ToggledSeq]] = None

    def __lt__(self, other) -> bool:
        # compare by toggle names
        if isinstance(other, ToggledGroup):
            return "".join(sorted(self.toggles_)) < "".join(sorted(other.toggles_))
        else:
            return False

    @classmethod
    def from_toggle_group_and_item(
        cls,
        toggled_group: "ToggledGroup",
        item: Union[ToggledMap, ToggledSeq],
        typ: ToggledBlockType,
        toggles: Mapping[str, bool],
    ) -> "ToggledGroup":
        if typ is ToggledBlockType.elif_:
            # TODO: validate toggle names and values uniqueness
            assert isinstance(toggled_group.elif_bodies, tuple)
            elif_groups = toggled_group.elif_bodies + (
                cls(body=item, toggles_=toggles, elif_bodies=None),
            )
            return evolve(toggled_group, elif_bodies=elif_groups)
        elif typ is ToggledBlockType.else_:
            assert (
                toggled_group.else_body is None
            ), f"Cannot set else_body to {toggled_group}, else_body is not empty."
            return evolve(toggled_group, else_body=item)
        else:
            raise ValueError(f"Unexpected toggled element of type {typ}")
