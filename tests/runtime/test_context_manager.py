from __future__ import annotations

from runtime.context_manager import ContextManager, RuntimeContext


def test_runtime_context_initial_state() -> None:
    context = RuntimeContext("root")
    assert context.name == "root"
    assert context.parent is None
    assert context.state == {}
    assert context.trace_id
    assert context.children == []


def test_runtime_context_state_operations() -> None:
    context = RuntimeContext("root")
    context.set("a", 1)
    context.update({"b": 2, "c": 3})
    assert context.get("a") == 1
    assert context.get("b") == 2
    assert context.get("missing") is None
    assert context.get("missing", 42) == 42
    assert context.state == {"a": 1, "b": 2, "c": 3}


def test_nested_context_inherits_parent_state() -> None:
    manager = ContextManager()
    parent = manager.push("parent")
    parent.set("shared", "value")
    child = manager.push("child")
    child.set("local", 10)
    assert child.parent is parent
    assert child.get("shared") == "value"
    assert child.get("local") == 10
    assert parent.get("local") is None


def test_nested_context_is_registered_as_child() -> None:
    manager = ContextManager()
    parent = manager.push("parent")
    child = manager.push("child")
    assert parent.children == [child]


def test_push_current_and_pop() -> None:
    manager = ContextManager()
    assert manager.current() is None
    first = manager.push("first")
    second = manager.push("second")
    assert manager.current() is second
    assert manager.pop() is second
    assert manager.current() is first
    assert manager.pop() is first
    assert manager.current() is None
    assert manager.pop() is None


def test_context_manager_state_proxy() -> None:
    manager = ContextManager()
    manager.push("root")
    manager.set("x", 10)
    manager.update({"y": 20})
    assert manager.get("x") == 10
    assert manager.get("y") == 20
    assert manager.get("missing", "default") == "default"


def test_scope_pushes_and_pops_context() -> None:
    manager = ContextManager()
    assert manager.current() is None
    with manager.scope("task") as context:
        assert manager.current() is context
        assert context.name == "task"
    assert manager.current() is None


def test_scope_nested_contexts() -> None:
    manager = ContextManager()
    with manager.scope("outer") as outer:
        with manager.scope("inner") as inner:
            assert manager.current() is inner
            assert inner.parent is outer
        assert manager.current() is outer
    assert manager.current() is None


def test_snapshot() -> None:
    manager = ContextManager()
    manager.push("root")
    manager.set("x", 1)
    manager.push("child")
    snapshot = manager.snapshot()
    assert snapshot["depth"] == 2
    assert snapshot["current"]["name"] == "child"
    assert len(snapshot["stack"]) == 2


def test_clear() -> None:
    manager = ContextManager()
    manager.push("root")
    manager.push("child")
    manager.clear()
    assert manager.current() is None
    assert manager.snapshot()["depth"] == 0
