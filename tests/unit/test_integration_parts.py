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
    "test_work_names.py": "works",
    "test_release_search.py": "releases",
    "test_release_manual.py": "releases",
    "test_release_jobs.py": "releases",
    "test_release_trackers.py": "releases",
    "test_release_filters.py": "releases",
    "test_session.py": "auth",
    "test_sign_in.py": "auth",
    "test_settings.py": "settings",
    "test_settings_tests.py": "settings",
    "test_download_send.py": "downloads",
    "test_download_follow.py": "downloads",
    "test_download_retry.py": "downloads",
    "test_download_manual.py": "downloads",
}
FILE_BLOCKS: Final = {
    "test_errors.py": "security_errors",
    "test_health.py": "security_health",
    "test_http_headers.py": "security_headers",
    "test_logging.py": "security_logging",
    "test_migrations.py": "security_migrations",
    "test_work_search.py": "works_search",
    "test_work_sources.py": "works_sources",
    "test_work_names.py": "works_names_language",
    "test_release_search.py": "releases_search",
    "test_release_manual.py": "releases_manual",
    "test_release_jobs.py": "releases_jobs",
    "test_release_trackers.py": "releases_trackers",
    "test_release_filters.py": "releases_filters",
    "test_session.py": "auth_session",
    "test_sign_in.py": "auth_sign_in",
    "test_settings.py": "settings_store",
    "test_settings_tests.py": "settings_tests",
    "test_download_send.py": "downloads_send",
    "test_download_follow.py": "downloads_follow",
    "test_download_retry.py": "downloads_retry",
    "test_download_manual.py": "downloads_manual",
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
