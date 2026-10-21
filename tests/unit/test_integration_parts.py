"""The parts and the blocks of the integration suite: every file of `tests/integration/` carries
the mark of its part, a file of a part of several files the mark of its block too, and
`pyproject.toml` declares them all. Nothing is collected nor run: the files are read as text."""

import ast
import tomllib
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
SUITE: Final = ROOT / "tests" / "integration"
PARTS: Final = {
    "test_errors.py": "security",
    "test_health.py": "security",
    "test_http_headers.py": "security",
    "test_logging.py": "security",
    "test_migrations.py": "security",
    "test_pages.py": "pages",
    "test_work_search.py": "works",
    "test_work_sources.py": "works",
}
FILE_BLOCKS: Final = {
    "test_errors.py": "security_errors",
    "test_health.py": "security_health",
    "test_http_headers.py": "security_headers",
    "test_logging.py": "security_logging",
    "test_migrations.py": "security_migrations",
    "test_work_search.py": "works_search",
    "test_work_sources.py": "works_sources",
}


def marks_of(path: Path) -> list[str]:
    """The names of the marks of the module-level `pytestmark` of `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "pytestmark"
        ):
            values = node.value.elts if isinstance(node.value, ast.List) else [node.value]
            return [value.attr for value in values if isinstance(value, ast.Attribute)]
    return []


def declared() -> set[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers: list[str] = config["tool"]["pytest"]["markers"]
    return {marker.split(":", 1)[0] for marker in markers}


def test_every_file_of_the_suite_is_in_the_tables() -> None:
    assert {path.name for path in SUITE.glob("test_*.py")} == set(PARTS)


def test_every_file_carries_its_part_and_its_block() -> None:
    for name, part in PARTS.items():
        expected = [part] + ([FILE_BLOCKS[name]] if name in FILE_BLOCKS else [])
        assert marks_of(SUITE / name) == expected, name


def test_every_mark_is_declared() -> None:
    assert set(PARTS.values()) | set(FILE_BLOCKS.values()) == declared()
