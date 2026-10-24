"""The layers of ADR 0004, checked on the source of shelfdrop: ruff cannot see them."""

import ast
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Final

import shelfdrop

ROOT: Final = Path(shelfdrop.__file__).resolve().parent.parent
MIGRATIONS: Final = "shelfdrop/db/migrations/versions/"
# The tests of the connections: the one file of the settings that calls the clients.
PROBES: Final = "shelfdrop/settings/probes.py"
FRAMEWORKS: Final = frozenset({"fastapi", "starlette", "wireup"})
WIREUP_IMPORTERS: Final = frozenset(
    {"shelfdrop/container.py", "shelfdrop/main.py", "shelfdrop/http/dependencies.py"}
)
# The packages of the domain: no framework, no HTTP layer.
DOMAIN: Final = (
    "shelfdrop/accounts/",
    "shelfdrop/auth/",
    "shelfdrop/clients/",
    "shelfdrop/works/",
    "shelfdrop/releases/",
    "shelfdrop/downloads/",
    "shelfdrop/journal/",
    "shelfdrop/placement/",
    "shelfdrop/ranger/",
    "shelfdrop/uploads/",
    "shelfdrop/library/",
    "shelfdrop/waiting/",
    "shelfdrop/settings/",
    "shelfdrop/tokens/",
    "shelfdrop/utils/",
    "shelfdrop/db/",
    "shelfdrop/logging/",
    "shelfdrop/logs/",
)


@cache
def sources() -> dict[str, ast.Module]:
    """The parsed `shelfdrop/**/*.py` files, without the Alembic revisions, by POSIX path."""
    trees: dict[str, ast.Module] = {}
    for path in sorted((ROOT / "shelfdrop").rglob("*.py")):
        key = path.relative_to(ROOT).as_posix()
        if not key.startswith(MIGRATIONS):
            trees[key] = ast.parse(path.read_text(encoding="utf-8"), filename=key)
    return trees


def imported(tree: ast.Module) -> list[str]:
    """Every module a file imports; a relative import fails the test."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports are not allowed"
            assert node.module is not None
            found.append(node.module)
    return found


def offenders(selected: Callable[[str], bool], forbidden: Callable[[str], bool]) -> list[str]:
    return [
        f"{path}: {module}"
        for path, tree in sources().items()
        if selected(path)
        for module in imported(tree)
        if forbidden(module)
    ]


def test_the_domain_never_imports_a_framework() -> None:
    assert (
        offenders(
            lambda path: path.startswith(DOMAIN), lambda module: module.split(".")[0] in FRAMEWORKS
        )
        == []
    )


def test_the_domain_never_imports_the_http_layer() -> None:
    assert (
        offenders(
            lambda path: path.startswith(DOMAIN),
            lambda module: module.startswith(
                ("shelfdrop.http", "shelfdrop.modules", "shelfdrop.main")
            ),
        )
        == []
    )


def test_only_the_composition_and_the_routers_import_wireup() -> None:
    assert (
        offenders(
            lambda path: path not in WIREUP_IMPORTERS and not path.endswith("/router.py"),
            lambda module: module.split(".")[0] == "wireup",
        )
        == []
    )


def test_the_routers_never_touch_the_database() -> None:
    assert (
        offenders(
            lambda path: path.startswith("shelfdrop/modules/"),
            lambda module: (
                module.split(".")[0] == "sqlalchemy" or module.startswith("shelfdrop.db")
            ),
        )
        == []
    )


def test_the_utilities_import_the_standard_library_alone() -> None:
    assert (
        offenders(
            lambda path: path.startswith("shelfdrop/utils/"),
            lambda module: module.split(".")[0] in {"shelfdrop", "httpx", "pydantic", "sqlalchemy"},
        )
        == []
    )


def test_only_the_service_and_the_composition_import_the_clients() -> None:
    assert (
        offenders(
            lambda path: (
                path not in ("shelfdrop/container.py", PROBES)
                and not path.startswith("shelfdrop/works/")
            ),
            lambda module: module.startswith("shelfdrop.works.clients"),
        )
        == []
    )


def test_only_the_releases_and_the_composition_import_the_prowlarr_client() -> None:
    assert (
        offenders(
            lambda path: (
                path not in ("shelfdrop/container.py", PROBES)
                and not path.startswith("shelfdrop/releases/")
            ),
            lambda module: module.startswith("shelfdrop.releases.clients"),
        )
        == []
    )


def test_the_works_the_releases_and_the_downloads_never_import_the_settings() -> None:
    assert (
        offenders(
            lambda path: path.startswith(
                ("shelfdrop/works/", "shelfdrop/releases/", "shelfdrop/downloads/")
            ),
            lambda module: module.startswith("shelfdrop.settings"),
        )
        == []
    )


def test_only_the_domains_that_call_a_service_and_the_composition_import_its_client() -> None:
    assert (
        offenders(
            lambda path: (
                path not in ("shelfdrop/container.py", PROBES)
                and not path.startswith(
                    (
                        "shelfdrop/auth/",
                        "shelfdrop/downloads/",
                        "shelfdrop/journal/",
                        "shelfdrop/placement/",
                        "shelfdrop/library/",
                        "shelfdrop/clients/",
                    )
                )
            ),
            lambda module: module.startswith("shelfdrop.clients"),
        )
        == []
    )
