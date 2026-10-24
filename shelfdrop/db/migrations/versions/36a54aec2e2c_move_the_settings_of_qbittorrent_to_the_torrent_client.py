"""Move the settings of qBittorrent to the torrent client.

The address of qui and the key of its client proxy (`qbittorrent.url`, `qbittorrent.api_key`)
become those of the torrent client (`torrent.url`, `torrent.api_key`), and an installation that
had saved either gets the client `qui`: it sends as before. The key keeps its sealing: it opens
under its former name until it is saved again (shelfdrop.settings.catalog.FORMER_NAMES). The audit
keeps the names it had.

Back down, the address and the key go back to their former names, the other settings of the
torrent client are dropped; a key saved again since was sealed under its new name, and does not
open there.

Revision ID: 36a54aec2e2c
Revises: fbd3a6ccd5f7
Create Date: 2026-10-24 13:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "36a54aec2e2c"
down_revision: str | Sequence[str] | None = "fbd3a6ccd5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE settings SET key = 'torrent.url' WHERE key = 'qbittorrent.url'"
        " AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'torrent.url')"
    )
    op.execute(
        "UPDATE secrets SET key = 'torrent.api_key' WHERE key = 'qbittorrent.api_key'"
        " AND NOT EXISTS (SELECT 1 FROM secrets WHERE key = 'torrent.api_key')"
    )
    # The client `qui` for an installation that saved its address or its key, dated by them.
    op.execute(
        "INSERT OR IGNORE INTO settings (key, value, updated_at, updated_by)"
        " SELECT 'torrent.client', '\"qui\"', (SELECT MAX(updated_at) FROM ("
        " SELECT updated_at FROM settings WHERE key = 'torrent.url' AND value != 'null'"
        " UNION ALL SELECT updated_at FROM secrets WHERE key = 'torrent.api_key')), NULL"
        " WHERE EXISTS (SELECT 1 FROM settings WHERE key = 'torrent.url' AND value != 'null')"
        " OR EXISTS (SELECT 1 FROM secrets WHERE key = 'torrent.api_key')"
    )
    op.execute("DELETE FROM settings WHERE key = 'qbittorrent.url'")
    op.execute("DELETE FROM secrets WHERE key = 'qbittorrent.api_key'")


def downgrade() -> None:
    op.execute(
        "DELETE FROM settings WHERE (key LIKE 'torrent.%' AND key != 'torrent.url')"
        " OR key = 'qbittorrent.url'"
    )
    op.execute("DELETE FROM secrets WHERE key IN ('torrent.password', 'qbittorrent.api_key')")
    op.execute("UPDATE settings SET key = 'qbittorrent.url' WHERE key = 'torrent.url'")
    op.execute("UPDATE secrets SET key = 'qbittorrent.api_key' WHERE key = 'torrent.api_key'")
