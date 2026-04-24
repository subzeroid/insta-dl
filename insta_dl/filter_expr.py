"""Safe evaluation of user-supplied post-filter expressions.

Accepts a restricted subset of Python (logical operators, comparisons, name
lookups in a sealed namespace) and rejects anything else at compile time —
no attribute access, no subscription, no function calls, no lambdas. The
compiled predicate runs against a `Post` with `__builtins__` stripped.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import Post

_ALLOWED_NODES: frozenset[type[ast.AST]] = frozenset(
    {
        ast.Expression,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.UnaryOp,
        ast.Not,
        ast.USub,
        ast.UAdd,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.IfExp,
        ast.Tuple,
        ast.List,
        ast.Set,
    }
)


class FilterExprError(ValueError):
    """Raised when the expression uses disallowed syntax or unknown names."""


_NAMESPACE_KEYS = frozenset(
    {
        "likes",
        "comments",
        "caption",
        "code",
        "username",
        "location",
        "taken_at",
        "year",
        "month",
        "day",
        "is_video",
        "is_photo",
        "is_album",
        "True",
        "False",
        "None",
    }
)


def _validate(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise FilterExprError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in _NAMESPACE_KEYS:
            raise FilterExprError(f"unknown name: {node.id!r}")


def compile_filter(expr: str) -> Callable[[Post], bool]:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FilterExprError(f"invalid expression: {exc.msg}") from exc
    _validate(tree)
    code = compile(tree, "<post-filter>", "eval")

    def predicate(post: Post) -> bool:
        from .models import MediaType

        namespace: dict[str, Any] = {
            "likes": post.like_count or 0,
            "comments": post.comment_count or 0,
            "caption": post.caption or "",
            "code": post.code,
            "username": post.owner_username,
            "location": post.location_name or "",
            "taken_at": post.taken_at,
            "year": post.taken_at.year,
            "month": post.taken_at.month,
            "day": post.taken_at.day,
            "is_video": post.media_type == MediaType.VIDEO,
            "is_photo": post.media_type == MediaType.PHOTO,
            "is_album": post.media_type == MediaType.ALBUM,
        }
        return bool(eval(code, {"__builtins__": {}}, namespace))

    return predicate
