"""No name starts with an underscore (CLAUDE.md, Code conventions; ADR 0054), checked on every
Python file of the repository: ruff has no rule for it."""

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

import shelfdrop

ROOT: Final = Path(shelfdrop.__file__).resolve().parent.parent
PACKAGES: Final = ("shelfdrop", "agent/shelfdrop_agent", "protocol/shelfdrop_protocol", "tests")
DUNDER_MIN_LENGTH: Final = 5


def is_allowed(name: str) -> bool:
    """A name without a leading underscore, `_` alone (a value that is ignored) or a dunder
    (`__init__`)."""
    is_dunder = len(name) >= DUNDER_MIN_LENGTH and name.startswith("__") and name.endswith("__")
    return name == "_" or not name.startswith("_") or is_dunder


def names(node: ast.AST) -> Sequence[str | None]:
    """The names `node` binds or reads. A keyword argument of a call and the module path of an
    import are left out: a library imposes them (`Settings(_env_file=None)`)."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.TypeVar,
            ast.ParamSpec,
            ast.TypeVarTuple,
        ),
    ):
        return [node.name]
    if isinstance(node, ast.Import):
        return [alias.asname for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [alias.asname or alias.name for alias in node.names]
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return [node.name]
    if isinstance(node, ast.MatchMapping):
        return [node.rest]
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return node.names
    return []


def offenders() -> list[str]:
    """`path:line: name` for every name that starts with an underscore, sorted."""
    found: set[str] = set()
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            found.update(
                f"{relative}:{getattr(node, 'lineno', 0)}: {name}"
                for node in ast.walk(tree)
                for name in names(node)
                if name is not None and not is_allowed(name)
            )
            found.update(
                f"{relative}:0: {part}"
                for part in path.relative_to(ROOT).with_suffix("").parts
                if not is_allowed(part)
            )
    return sorted(found)


@pytest.mark.parametrize(
    ("name", "allowed"),
    [
        ("session", True),
        ("_", True),
        ("__init__", True),
        ("list_", True),
        ("_session", False),
        ("__mangled", False),
        ("__", False),
        ("____", False),
    ],
)
def test_only_a_bare_underscore_and_dunders_may_start_with_an_underscore(
    name: str, allowed: bool
) -> None:
    assert is_allowed(name) is allowed


def test_names_are_read_from_definitions_uses_and_imports_but_not_from_keywords() -> None:
    source = (
        "from library import _imported, other as _alias\n"
        "import library._module\n"
        "class _Class:\n"
        "    def _method(self, _parameter: int) -> None:\n"
        "        self._attribute = _parameter\n"
        "call(_keyword=None)\n"
    )

    found = {name for node in ast.walk(ast.parse(source)) for name in names(node)}

    assert {"_imported", "_alias", "_Class", "_method", "_parameter", "_attribute"} <= found
    assert "_keyword" not in found
    assert "_module" not in found


def test_no_name_starts_with_an_underscore() -> None:
    found = offenders()

    assert not found, "\n".join(found)
