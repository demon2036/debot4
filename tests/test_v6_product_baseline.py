from debot4.v6.explosion.product_baseline import _sample_target
from debot4.v6.product_leak import PublicResourceTarget


TARGET = PublicResourceTarget(
    "xai-bot-page", "x:spacexai", "official_company",
    "https://x.ai/bot", ("grok bot",),
)


class Monitor:
    def __init__(self, result=(), error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def poll(self, _target):
        if self.error is not None:
            raise self.error
        return self.result


def test_product_target_keeps_success_count() -> None:
    result = _sample_target(Monitor((object(), object())), TARGET)

    assert result.events == 2
    assert result.ok is True


def test_product_target_sanitizes_failures_to_type() -> None:
    result = _sample_target(Monitor(error=RuntimeError("secret")), TARGET)

    assert result.events == 0
    assert result.error_type == "RuntimeError"
    assert result.ok is False
