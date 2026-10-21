"""The registry of the ORM models: import them from here, so Base.metadata knows every table."""

from shelfdrop.db.models.cached_work import CachedWork
from shelfdrop.db.models.filter_rule import FilterRule
from shelfdrop.db.models.release_answer import ReleaseAnswer
from shelfdrop.db.models.setting import Setting
from shelfdrop.db.models.source_answer import SourceAnswer
from shelfdrop.db.models.tracker import Tracker

__all__ = ["CachedWork", "FilterRule", "ReleaseAnswer", "Setting", "SourceAnswer", "Tracker"]
