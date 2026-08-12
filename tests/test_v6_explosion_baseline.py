from debot4.v6.ecosystem_authority import AuthorityNode
from debot4.v6.explosion.baseline import _sample_target


NODE = AuthorityNode(
    "bot",
    "2085838061347217408",
    "Grok Bot",
    "official_product",
    "https://x.com/bot",
)


class StubIdentity:
    def __init__(self, result=(), error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def poll(self, *_args, **_kwargs):
        if self.error is not None:
            raise self.error
        return self.result


class StubRelationships:
    def __init__(self, result=(), error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def poll(self, *_args, **_kwargs):
        if self.error is not None:
            raise self.error
        return self.result


def test_target_keeps_relationship_result_when_identity_fails() -> None:
    result = _sample_target(
        NODE,
        StubIdentity(error=RuntimeError("profile failed")),
        StubRelationships(result=(object(), object())),
    )

    assert result.identity_events == 0
    assert result.relationship_events == 2
    assert result.error_types == ("identity:RuntimeError",)
    assert result.ok is False


def test_target_keeps_identity_result_when_relationship_fails() -> None:
    result = _sample_target(
        NODE,
        StubIdentity(result=(object(),)),
        StubRelationships(error=ValueError("following failed")),
    )

    assert result.identity_events == 1
    assert result.relationship_events == 0
    assert result.error_types == ("relationship:ValueError",)
    assert result.as_dict()["ok"] is False


def test_target_can_sample_identity_without_slow_relationships() -> None:
    result = _sample_target(
        NODE,
        StubIdentity(result=(object(),)),
        None,
    )

    assert result.identity_events == 1
    assert result.relationship_events is None
    assert result.ok is True


def test_target_can_sample_relationships_without_identity() -> None:
    result = _sample_target(
        NODE,
        None,
        StubRelationships(result=(object(), object())),
    )

    assert result.identity_events is None
    assert result.relationship_events == 2
    assert result.ok is True
