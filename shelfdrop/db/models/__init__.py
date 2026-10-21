"""The registry of the ORM models: import them from here, so Base.metadata knows every table."""

from shelfdrop.db.models.audit_entry import AuditEntry
from shelfdrop.db.models.cached_work import CachedWork
from shelfdrop.db.models.download import Download
from shelfdrop.db.models.event import Event
from shelfdrop.db.models.filter_rule import FilterRule
from shelfdrop.db.models.library_task import LibraryTask
from shelfdrop.db.models.login_session import LoginSession
from shelfdrop.db.models.place_item import PlaceItem
from shelfdrop.db.models.release_answer import ReleaseAnswer
from shelfdrop.db.models.secret import Secret
from shelfdrop.db.models.setting import Setting
from shelfdrop.db.models.shelf_file import ShelfFile
from shelfdrop.db.models.source_answer import SourceAnswer
from shelfdrop.db.models.tracker import Tracker
from shelfdrop.db.models.waiting_search import WaitingSearch

__all__ = [
    "AuditEntry",
    "CachedWork",
    "Download",
    "Event",
    "FilterRule",
    "LibraryTask",
    "LoginSession",
    "PlaceItem",
    "ReleaseAnswer",
    "Secret",
    "Setting",
    "ShelfFile",
    "SourceAnswer",
    "Tracker",
    "WaitingSearch",
]
