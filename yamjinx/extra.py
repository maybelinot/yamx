# not very supported pieces of functionality

from typing import Any, Set

from yamjinx.containers.data import ToggledGroup, ToggledMap, ToggledSeq


def extract_toggles(obj: Any, toggles: Set[str] = set()):
    if isinstance(obj, ToggledMap):
        for value in obj.values():
            toggles |= extract_toggles(value)
    elif isinstance(obj, ToggledSeq):
        for value in obj:
            toggles |= extract_toggles(value)
    elif isinstance(obj, ToggledGroup):
        toggles |= set(obj.toggles_)
        toggles |= extract_toggles(obj.body)
        toggles |= extract_toggles(obj.else_body)
        for elif_body in obj.elif_bodies or []:
            toggles |= extract_toggles(elif_body)
    else:
        return toggles

    return toggles
