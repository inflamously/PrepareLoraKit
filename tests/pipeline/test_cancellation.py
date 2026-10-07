import pytest

from prepare_lora_kit.cancellation import CancelledRun, cancellable


def test_cancellable_yields_every_item_when_not_cancelled():
    calls = []

    result = list(cancellable(["a", "b", "c"], lambda: calls.append(1)))

    assert result == ["a", "b", "c"]
    assert len(calls) == 3


def test_cancellable_checks_before_each_item_is_handed_out():
    seen = []

    def cancel_on_third():
        if len(seen) == 2:
            raise CancelledRun()

    iterator = cancellable([1, 2, 3, 4], cancel_on_third)
    seen.append(next(iterator))
    seen.append(next(iterator))

    with pytest.raises(CancelledRun):
        next(iterator)

    assert seen == [1, 2]


def test_cancellable_does_not_check_an_empty_iterable():
    def fail():
        raise AssertionError("cancel check should not run")

    assert list(cancellable([], fail)) == []


def test_cancellable_is_lazy():
    calls = []

    iterator = cancellable(iter([1, 2]), lambda: calls.append(1))

    assert calls == []
    assert next(iterator) == 1
    assert calls == [1]
