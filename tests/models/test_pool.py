"""LoadedModels: shared loads, refcounted release."""

from __future__ import annotations

import threading
import time

import pytest

from haybale_models.pool import LoadedModels
from haybale_models.states.models_state import ModelsState


def test_two_holders_share_one_load() -> None:
    pool = LoadedModels()
    loads: list[int] = []
    released: list[object] = []
    h1, h2 = object(), object()

    def load() -> object:
        loads.append(1)
        return object()

    a = pool.acquire(("s", "cpu"), h1, load, released.append)
    b = pool.acquire(("s", "cpu"), h2, load, released.append)
    assert a is b
    assert loads == [1]
    pool.release(h1)
    assert released == []
    pool.release(h2)
    assert released == [a]
    assert pool.entries() == []


def test_one_holder_acquiring_twice_counts_once() -> None:
    pool = LoadedModels()
    released: list[object] = []
    h = object()
    pool.acquire(("s", "v"), h, object, released.append)
    pool.acquire(("s", "v"), h, object, released.append)
    assert pool.entries()[0].holders == 1
    pool.release(h)
    assert len(released) == 1


def test_different_variants_are_separate_loads() -> None:
    pool = LoadedModels()
    h = object()
    a = pool.acquire(("s", "cpu"), h, object, lambda _: None)
    b = pool.acquire(("s", "gpu"), h, object, lambda _: None)
    assert a is not b
    assert len(pool.entries()) == 2


def test_concurrent_acquire_loads_once() -> None:
    pool = LoadedModels()
    loads: list[int] = []
    results: list[object] = []

    def load() -> object:
        loads.append(1)
        time.sleep(0.05)
        return object()

    def work() -> None:
        results.append(pool.acquire(("s", "v"), object(), load, lambda _: None))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert loads == [1]
    assert len({id(r) for r in results}) == 1
    assert pool.entries()[0].holders == 8


def test_raising_load_leaves_no_entry() -> None:
    pool = LoadedModels()

    def boom() -> object:
        raise ValueError("no")

    with pytest.raises(ValueError, match="no"):
        pool.acquire(("s", "v"), object(), boom, lambda _: None)
    assert pool.entries() == []
    assert pool.acquire(("s", "v"), object(), lambda: 7, lambda _: None) == 7


def test_release_exception_is_logged_not_raised() -> None:
    pool = LoadedModels()
    h = object()

    def bad(_: object) -> None:
        raise RuntimeError("x")

    pool.acquire(("s", "v"), h, object, bad)
    pool.release(h)
    assert pool.entries() == []


def test_release_all_on_disable() -> None:
    state = ModelsState()
    released: list[object] = []
    a = state.pool.acquire(("s", "v"), object(), object, released.append)
    state.on_disable()
    assert released == [a]
    assert state.pool.entries() == []
