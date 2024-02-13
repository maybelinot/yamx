from typing import Optional, Union

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.tokens import CommentToken

from yamx.constants import DEDUPLICATOR
from yamx.containers.data import ConditionalMap

UNIQUE_CNT: int = 0


def render_conditional_map(
    cm: CommentedMap,
    data: ConditionalMap,
    before: Optional[str],
    after: Optional[str],
    indent: int,
    sort_keys: bool,
) -> CommentedMap:
    """
    CommentedMap object has following comment attributes:

    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@    cm.ca.comment    @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cm.ca.comment: [comment1, [comment2, ...], [comment3, ...]] = None
        Denote 3 types of comments:
        1. single comment placed before first key-value and `-` if it's an item of commentedSeq,
           new line is added at the end if missing.
            type: Optional[CommentToken]
        2. multi comment placed before first key-value and after `-` if it's an item of commentedSeq
            type: Optional[List[CommentToken]]]
        3. multi comment placed after all key-values of the mapping
            type: Optional[List[CommentToken]]]

        Let's see how it works on the example:

        > cm = CommentedMap({"first":1, "second":2})
        > mark = CommentMark(0) # mark represents indentation
        > cm.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]

    NOTE: Rendering of the comment varies based on parent object annotation.
    The reason is that during represenation `comment` attribute is propagated
    to relevant `items` attribute of the parent object (see `items` comment attribute)

    ====== CommentedSeq parent object =======
        > yaml.dump_to_string(CommentedSeq(cm))

        # COMMENT2
        - # COMMENT1
        first: 1
        second: 2
        # COMMENT3


    ====== CommentedMap parent object =======
        > yaml.dump_to_string(CommentedMap(map=cm))

        map: # COMMENT1
        # COMMENT2
        first: 1
        second: 2
        # COMMENT3


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@     cm.ca.items     @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cm.ca.items: Dict[int, [comment1, [comment2, ...], comment3, [comment4,...]]] = {}
        Denotes 4 types of comments attached to particular element of a key-value
        1. single comment (new line is added at the end if missing)
            position: right after key, but before `:`
            type: Optional[CommentToken]
        2. multi comment placed before key
            type: Optional[List[CommentToken]]]
        3. single comment (new line is added at the end if missing)
            position: right after `:` if value is of type map or seq, otherwise after value
            type: Optional[CommentToken]
        4. multi comment (ignored if value is a scalar)
            position: before value
            type: Optional[List[CommentToken]]]

        Key of ca.items dict is a key of key-value pair in a mapping


        let's see how it works on following example:
        > cm = CommentedMap({"first": 1})
        > cm.ca.items["first"] = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            CommentToken("# COMMENT3", mark),
            [CommentToken("# COMMENT4\n", mark)],
        ]
        > outer_map = CommentedMap(outer=cm)
        > print(yaml.dump_to_string(outer_map))

        outer:
        # COMMENT2
        first # COMMENT1
        : 1 # COMMENT3

    NOTE: items annotation of parent object can CONFLICT with `comment` (see above)
    annotation of a children:


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@     cm.ca.end     @@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    doesn't seem to have any specific usage for CommentedMap
    """
    global UNIQUE_CNT

    # TODO: return if empty
    if len(data) == 0:
        raise NotImplementedError

    # TODO: move sorting to different place
    if sort_keys:
        iter_data = enumerate(
            # make sure to use original key for sorting
            sorted(data.items(), key=lambda kv: kv[0].split(DEDUPLICATOR)[0])
        )
    else:
        iter_data = enumerate(data.items())

    for idx, (data_key, data_value) in iter_data:
        if data_key in cm:
            # TODO: log proper warning + handle deduplicated keys
            print(f"warning: Duplicate '{data_key}' key encountered")
        prev_data_key = data_key
        # to avoid keys duplication - adding unique suffix
        if DEDUPLICATOR not in data_key:
            data_key = f"{data_key}{DEDUPLICATOR}{UNIQUE_CNT}"
            UNIQUE_CNT += 1

        # move prev comment annotation to cm
        if prev_data_key in data.ca.items:
            cm.ca.items.update({data_key: data.ca.items[prev_data_key]})

        if idx == 0:
            first_data_key = data_key
        cm.update({data_key: data_value})

    last_data_key = data_key
    # when conditional block consist of multiple elements we need to
    # attach before and after comment to different items

    # first attaching before comment to the first added item
    if before is not None:
        _annotate_commented_map_scalar_item(
            commented_data=cm,
            data_key=first_data_key,
            before=before,
            after=None,
            indent=indent,
        )

    # now attaching after comment to the last added item
    if after is not None:
        if isinstance(cm[last_data_key], CommentedMap):
            # propagate after comment all the way to the outermost element of the structure
            _set_after_map_comment(cm=cm[last_data_key], after=after, indent=indent)
        elif isinstance(cm[last_data_key], CommentedSeq) and len(cm[last_data_key]):
            _annotate_commented_seq_commented_item(
                item=cm[last_data_key],
                before=None,
                after=after,
                indent=indent,
            )
        else:
            # otherwise value is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_map_scalar_item(
                commented_data=cm,
                data_key=last_data_key,
                before=None,
                after=after,
                indent=indent,
            )


def _annotate_commented_map_scalar_item(
    commented_data: Union[CommentedMap, CommentedSeq],
    data_key: Union[str, int],
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """Annotating simple scalar value
    Comment annotations are attached to parent object ca.items structure
    """
    # create comment tokens
    mark = CommentMark(indent)
    before_comment = before and CommentToken(f"# {before}\n", mark)
    # NOTE: comment is prefixed with new line as it is attached after value
    after_comment = after and CommentToken(f"\n{' '*indent}# {after}", mark)

    prev_ca = commented_data.ca.items.get(data_key)
    # item could be already annotated, let's extract the comments and merge them
    if prev_ca:
        # prepare after_comments
        if after_comment and prev_ca[2]:
            after_comments = _merge_comments(prev_ca[2], after_comment)
        elif after_comment:
            after_comments = after_comment
        else:
            after_comments = prev_ca[2]
        # prepare before_comments
        if before_comment is not None:
            before_comments = [before_comment, *(prev_ca[1] or [])]
        else:
            before_comments = prev_ca[1]

        new_ca = [
            None,
            before_comments,
            after_comments,
            None,
        ]
    else:
        new_ca = [None, before_comment and [before_comment], after_comment, None]

    commented_data.ca.items[data_key] = new_ca


def _set_after_map_comment(cm, after: str, indent: int) -> None:
    """Recursively propagates after comment to the last map item"""
    # in case CommentedMap is empty - attaching comment to cm.ca
    mark = CommentMark(indent)
    after_comment = CommentToken(f"\n{' '*indent}# {after}", mark)

    if len(cm) == 0:
        cm.ca.comment = [after_comment, []]
        return
    # otherwise, propagating deeper
    last_map_key = next(reversed(cm))
    if isinstance(cm[last_map_key], CommentedMap):
        _set_after_map_comment(cm[last_map_key], after, indent=indent)
    elif isinstance(cm[last_map_key], CommentedSeq) and len(cm[last_map_key]):
        _annotate_commented_seq_commented_item(
            item=cm[last_map_key],
            before=None,
            after=after,
            indent=indent,
        )
    else:
        try:
            cm.ca.items[last_map_key][2] = _merge_comments(
                cm.ca.items[last_map_key][2], after_comment
            )
        except KeyError:
            cm.ca.items[last_map_key] = [None, None, after_comment, None]


def _merge_comments(comment1: CommentToken, comment2: CommentToken) -> CommentToken:
    """Used to merge 2 comments into a single CommentToken object
    NOTE: only single-line comments are supported
    """
    assert comment1.value.startswith("\n")
    assert comment2.value.startswith("\n")

    indent = min(comment1.column, comment2.column)
    mark = CommentMark(indent)

    return CommentToken(
        f"{comment1.value}{comment2.value}",
        mark,
    )


def render_conditional_seq(
    cs: CommentedSeq,
    data: CommentedSeq,
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """
    CommentedSeq object has following comment attributes:

    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@    cs.ca.comment    @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cs.ca.comment: [comment1, [comment2, ...], [comment3, ...]] = None
        Denote 3 types of comments:
        1. single comment placed right before `-` sign (new line is added at the end if missing)
            type: Optional[CommentToken]
        2. multi comment placed right after `-` sign
            type: Optional[List[CommentToken]]]
        3. multi comment placed after all elements of the sequence
            type: Optional[List[CommentToken]]]
            note: comment is placed only in case of non empty sequence

        Let's see how it works on the example:

        > cs = CommentedSeq([1,2])
        > mark = CommentMark(0) # mark represents indentation
        > cs.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]

    NOTE: Rendering of the comment varies based parent object annotation.
    The reason is that during represenation `comment` attribute is propagated
    to relevant `items` attribute of the parent object (see `items` comment attribute)

    ====== CommentedSeq parent object =======
        > yaml.dump_to_string(CommentedSeq(cs))

        # COMMENT2
        - # COMMENT1
            - 1
            - 2
        # COMMENT3


    ====== CommentedMap parent object =======
        > yaml.dump_to_string(CommentedMap(list=cs))

        list: # COMMENT1
        # COMMENT2
        - 1
        - 2
        # COMMENT3


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@     cs.ca.items     @@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    cs.ca.items: Dict[int, [comment1, [comment2, ...]]] = {}
        Denotes 2 types of comments attached to particular element of a sequence
        1. single comment placed after seq item value
            type: Optional[CommentToken]
        2. multi comment placed before `-` sign (new line is added at the end if missing)
            type: Optional[List[CommentToken]]]
        Key of ca.items dict is an index of an element in the list


        let's see how it works on the example:
        > cs = CommentedSeq([1])
        > cs.ca.items[0] = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
        ]
        > yaml.dump_to_string(CommentedSeq(cs))

        # COMMENT2
        - 1 # COMMENT1

    NOTE: items annotation of parent object can CONFLICT with `comment` (see above)
    and `end` (see below) annotations of a children:

    If parent object has defined `items` annotation for particular element - following applies:

    1. Any item annotation from a parent object make representer ignore 3rd comment of children
    cs.ca.comment annotation

        > cs = CommentedSeq([1,2])
        > mark = CommentMark(0) # mark represents indentation
        > cs.ca.comment = [
            CommentToken("# COMMENT1", mark),
            [CommentToken("# COMMENT2\n", mark)],
            [CommentToken("# COMMENT3\n", mark)]
        ]
        parent_cs = CommentedSeq([cs])
        parent_cs.items[0] = [None, None]
        > yaml.dump_to_string(parent_cs)

        # COMMENT2
        - # COMMENT1
            - 1

    2. Once commented structure is representer certain modifications are happening to
        annotated structure:
        * comment1 of cs.comment anntotation is propagated to comment1 annotation
            of parent_cs.items[0]
        * the same logic applies to comment2 of cs.comment and parent_cs.items[0] respectively
            NOTE: Propagation is only happening to parent structure, not to the children
            NOTE: Propagation doesn't happen if parent_cs.items[0] is not defined
            NOTE: If both comments of parent_cs and cs are defined when attepmt to represent
                    a structure ASSERTION error is raised


    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@     cs.ca.end     @@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    doesn't seem to have any specific usage for CommentedSeq
    """

    first_item_pos = len(cs)
    last_item_pos = first_item_pos + len(data) - 1

    assert first_item_pos <= last_item_pos

    # NOTE: extend method will shift comment annotation of all comments with
    # ids higher than last element - we should extend first, annotate after
    cs.extend(data)
    # now we can extend cs.ca with annotation of newly added items
    # in order to do that we need to shift all indices by len of cs
    cs.ca.items.update(
        {first_item_pos + key: comment for key, comment in data.ca.items.items()}
    )
    # when conditional block consists of multiple elements we need to
    # attach before and after comment to different items

    # first attaching before comment to the first added item
    if before is not None:
        if isinstance(cs[first_item_pos], CommentedMap):
            _annotate_commented_map_scalar_item(
                commented_data=cs,
                data_key=first_item_pos,
                before=before,
                after=None,
                indent=indent,
            )
        elif isinstance(cs[first_item_pos], CommentedSeq):
            _annotate_commented_seq_commented_item(
                item=cs[first_item_pos],
                before=before,
                after=None,
                indent=indent,
            )
        else:
            # otherwise item is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_seq_scalar_item(
                cs=cs,
                item_idx=first_item_pos,
                before=before,
                after=None,
                indent=indent,
            )

    # now attaching after comment to the last added item
    if after is not None:
        if isinstance(cs[last_item_pos], CommentedMap):
            _set_after_map_comment(cm=cs[last_item_pos], after=after, indent=indent)
        elif isinstance(cs[last_item_pos], CommentedSeq) and len(cs[last_item_pos]):

            _annotate_commented_seq_commented_item(
                item=cs[last_item_pos],
                before=None,
                after=after,
                indent=indent,
            )
        else:
            # otherwise item is a simple scalar - setting annotation on items attribute of a
            # parent object
            _annotate_commented_seq_scalar_item(
                cs=cs,
                item_idx=last_item_pos,
                before=None,
                after=after,
                indent=indent,
            )


def _annotate_commented_seq_commented_item(
    item: CommentedSeq, before: Optional[str], after: Optional[str], indent: int
) -> None:
    """Annotating commented values
    Comment annotations are attached to actual item object ca.comment structure
    """
    mark = CommentMark(indent)
    # create comment tokens
    before_comment = before and [CommentToken(f"# {before}\n", mark)]
    after_comment = after and [CommentToken(f"# {after}\n", mark)]

    # item could be already annotated, let's extract the comments and merge them
    if prev_ca := item.ca.comment:
        new_ca = [
            None,
            # merge comments into list if it's not None
            ((before_comment or []) + (prev_ca[1] or [])) or None,
            ((prev_ca[2] or []) + (after_comment or [])) or None,
        ]
    else:
        new_ca = [
            None,
            # put comments into list if it's not None
            before_comment,
            after_comment,
        ]
    item.ca.comment = new_ca


def _annotate_commented_seq_scalar_item(
    cs: CommentedSeq,
    item_idx: int,
    before: Optional[str],
    after: Optional[str],
    indent: int,
) -> None:
    """Annotating simple scalar value
    Comment annotations are attached to parent object ca.items structure
    """
    # create comment tokens
    mark = CommentMark(indent)
    before_comment = before and CommentToken(f"# {before}\n", mark)
    # NOTE: comment is prefixed with new line as it is attached after value
    after_comment = after and CommentToken(f"\n{' '*indent}# {after}", mark)

    prev_ca = cs.ca.items.get(item_idx)
    # item could be already annotated, let's extract the comments and merge them
    if prev_ca:
        # prepare after_comments
        if after_comment and prev_ca[0]:
            after_comments = _merge_comments(prev_ca[0], after_comment)
        elif after_comment:
            after_comments = after_comment
        else:
            after_comments = prev_ca[0]
        # prepare before_comments
        if before_comment is not None:
            before_comments = [before_comment, *(prev_ca[1] or [])]
        else:
            before_comments = prev_ca[1]

        new_ca = [
            after_comments,
            before_comments,
        ]
    else:
        new_ca = [after_comment, before_comment and [before_comment]]

    cs.ca.items[item_idx] = new_ca
