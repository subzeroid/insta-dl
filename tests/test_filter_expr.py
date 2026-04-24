from __future__ import annotations

from datetime import UTC, datetime

import pytest

from insta_dl.filter_expr import FilterExprError, compile_filter
from insta_dl.models import MediaType, Post


def _post(**overrides) -> Post:
    defaults = {
        "pk": "p1",
        "code": "ABC123",
        "media_type": MediaType.PHOTO,
        "taken_at": datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC),
        "owner_pk": "1",
        "owner_username": "instagram",
        "caption": "sunset at the beach",
        "like_count": 150,
        "comment_count": 12,
        "location_name": "Malibu",
    }
    defaults.update(overrides)
    return Post(**defaults)


def test_simple_greater_than():
    keep = compile_filter("likes > 100")
    assert keep(_post(like_count=150)) is True
    assert keep(_post(like_count=50)) is False


def test_combined_and_or_not():
    keep = compile_filter("likes > 100 and not is_video")
    assert keep(_post(like_count=200, media_type=MediaType.PHOTO)) is True
    assert keep(_post(like_count=200, media_type=MediaType.VIDEO)) is False
    assert keep(_post(like_count=50, media_type=MediaType.PHOTO)) is False


def test_in_operator_on_caption():
    keep = compile_filter("'sunset' in caption")
    assert keep(_post(caption="sunset at the beach")) is True
    assert keep(_post(caption="morning coffee")) is False


def test_none_like_count_treated_as_zero():
    keep = compile_filter("likes >= 0")
    assert keep(_post(like_count=None)) is True
    assert compile_filter("likes > 0")(_post(like_count=None)) is False


def test_date_helpers():
    keep = compile_filter("year == 2026 and month >= 4")
    assert keep(_post()) is True
    assert keep(_post(taken_at=datetime(2026, 3, 1, tzinfo=UTC))) is False


def test_media_type_flags():
    assert compile_filter("is_photo")(_post(media_type=MediaType.PHOTO)) is True
    assert compile_filter("is_video")(_post(media_type=MediaType.VIDEO)) is True
    assert compile_filter("is_album")(_post(media_type=MediaType.ALBUM)) is True
    assert compile_filter("is_photo")(_post(media_type=MediaType.VIDEO)) is False


def test_tuple_membership():
    keep = compile_filter("username in ('instagram', 'meta')")
    assert keep(_post(owner_username="instagram")) is True
    assert keep(_post(owner_username="other")) is False


def test_ternary_if_expression():
    keep = compile_filter("(100 if is_video else 500) < likes")
    assert keep(_post(media_type=MediaType.VIDEO, like_count=150)) is True
    assert keep(_post(media_type=MediaType.PHOTO, like_count=150)) is False


def test_rejects_attribute_access():
    with pytest.raises(FilterExprError, match="disallowed syntax: Attribute"):
        compile_filter("caption.lower")


def test_rejects_subscript():
    with pytest.raises(FilterExprError, match="disallowed syntax: Subscript"):
        compile_filter("caption[0]")


def test_rejects_function_call():
    with pytest.raises(FilterExprError, match="disallowed syntax: Call"):
        compile_filter("len(caption) > 10")


def test_rejects_unknown_name():
    with pytest.raises(FilterExprError, match="unknown name: 'secret'"):
        compile_filter("secret > 0")


def test_rejects_dunder_escape():
    # Even without Attribute, __class__ style access is impossible without Attribute or Call.
    with pytest.raises(FilterExprError, match="disallowed syntax: Attribute"):
        compile_filter("caption.__class__")


def test_rejects_syntax_error():
    with pytest.raises(FilterExprError, match="invalid expression"):
        compile_filter("likes >")


def test_builtins_are_unavailable():
    # Even if someone sneaks in a known name that collides with a builtin, we
    # don't expose __builtins__ — so reliance on one would fail at eval-time.
    with pytest.raises(FilterExprError, match="unknown name"):
        compile_filter("__import__")
