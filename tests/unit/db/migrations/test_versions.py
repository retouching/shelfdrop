"""The revisions of shelfdrop/db/migrations/versions/ that carry rows, applied on a database in
memory: the rows before, the rows after."""

from collections.abc import Iterator
from typing import Final

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, create_engine

from shelfdrop.db.base import Base
from tests.unit.db.test_migrate import read_script

TORRENT_CLIENT: Final = "36a54aec2e2c"
SETTINGS: Final = Base.metadata.tables["settings"]
SECRETS: Final = Base.metadata.tables["secrets"]


@pytest.fixture
def connection() -> Iterator[Connection]:
    """The tables of the settings and of the secrets, empty."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[SETTINGS, SECRETS])
    with engine.begin() as opened:
        yield opened
    engine.dispose()


def run(connection: Connection, revision: str, step: str) -> None:
    """`upgrade` or `downgrade` of `revision`, on `connection`."""
    module = read_script().get_revision(revision).module
    with Operations.context(MigrationContext.configure(connection)):
        getattr(module, step)()


def setting(connection: Connection, key: str, value: str, at: int = 100) -> None:
    connection.exec_driver_sql("INSERT INTO settings VALUES (?, ?, ?, 'sylvain')", (key, value, at))


def secret(connection: Connection, key: str, at: int = 100) -> None:
    sealed = b"sealed-" + key.encode()
    connection.exec_driver_sql("INSERT INTO secrets VALUES (?, ?, ?, 'sylvain')", (key, sealed, at))


def settings_of(connection: Connection) -> dict[str, tuple[str, int]]:
    rows = connection.exec_driver_sql("SELECT key, value, updated_at FROM settings")
    return {key: (value, at) for key, value, at in rows}


def secrets_of(connection: Connection) -> dict[str, bytes]:
    rows = connection.exec_driver_sql("SELECT key, ciphertext FROM secrets")
    return {key: sealed for key, sealed in rows}


def test_the_settings_of_qbittorrent_become_those_of_the_client_qui(
    connection: Connection,
) -> None:
    setting(connection, "qbittorrent.url", '"http://qui:7476"', at=100)
    secret(connection, "qbittorrent.api_key", at=200)
    setting(connection, "prowlarr.url", '"http://prowlarr:9696"')
    secret(connection, "prowlarr.api_key")

    run(connection, TORRENT_CLIENT, "upgrade")

    assert settings_of(connection) == {
        "torrent.url": ('"http://qui:7476"', 100),
        "torrent.client": ('"qui"', 200),
        "prowlarr.url": ('"http://prowlarr:9696"', 100),
    }
    # The key moved as it is: sealed under its former name.
    assert secrets_of(connection) == {
        "torrent.api_key": b"sealed-qbittorrent.api_key",
        "prowlarr.api_key": b"sealed-prowlarr.api_key",
    }


def test_an_installation_without_qbittorrent_gets_no_client(connection: Connection) -> None:
    setting(connection, "qbittorrent.url", "null")
    setting(connection, "prowlarr.url", '"http://prowlarr:9696"')

    run(connection, TORRENT_CLIENT, "upgrade")

    assert settings_of(connection) == {
        "torrent.url": ("null", 100),
        "prowlarr.url": ('"http://prowlarr:9696"', 100),
    }


def test_the_key_alone_gives_the_client_qui(connection: Connection) -> None:
    secret(connection, "qbittorrent.api_key", at=300)

    run(connection, TORRENT_CLIENT, "upgrade")

    assert settings_of(connection) == {"torrent.client": ('"qui"', 300)}
    assert set(secrets_of(connection)) == {"torrent.api_key"}


def test_back_down_the_address_and_the_key_go_back_and_the_rest_goes(
    connection: Connection,
) -> None:
    setting(connection, "qbittorrent.url", '"http://qui:7476"')
    secret(connection, "qbittorrent.api_key")
    run(connection, TORRENT_CLIENT, "upgrade")
    setting(connection, "torrent.username", '"admin"')
    setting(connection, "torrent.folder.manga", '"/data/torrents/manga"')
    secret(connection, "torrent.password")

    run(connection, TORRENT_CLIENT, "downgrade")

    assert settings_of(connection) == {"qbittorrent.url": ('"http://qui:7476"', 100)}
    assert secrets_of(connection) == {"qbittorrent.api_key": b"sealed-qbittorrent.api_key"}
