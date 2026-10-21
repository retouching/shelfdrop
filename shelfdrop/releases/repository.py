"""ReleaseRepository: the cache of the answers of Prowlarr, the trackers, the filter rules and the
settings of the release search."""

import json
from collections.abc import Callable, Iterable
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from shelfdrop.db.models import AuditEntry, ReleaseAnswer, Setting
from shelfdrop.db.models import FilterRule as FilterRuleRow
from shelfdrop.db.models import Tracker as TrackerRow
from shelfdrop.releases.types import FilterRule, FoundRelease, Tracker
from shelfdrop.works.types import Kind

RELEASES: Final = TypeAdapter(tuple[FoundRelease, ...])
KINDS: Final = TypeAdapter(tuple[Kind, ...])


class ReleaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read_answer(self, key: str, now: int) -> tuple[tuple[FoundRelease, ...], float] | None:
        """The releases Prowlarr gave for `key` and when, unless they expired."""
        row = self.session.scalar(
            select(ReleaseAnswer).where(ReleaseAnswer.key == key, ReleaseAnswer.expires_at > now)
        )
        return None if row is None else (RELEASES.validate_json(row.releases), row.fetched_at)

    def save_answer(
        self, key: str, releases: tuple[FoundRelease, ...], fetched_at: float, expires_at: int
    ) -> None:
        self.session.merge(
            ReleaseAnswer(
                key=key,
                releases=RELEASES.dump_json(releases).decode(),
                fetched_at=fetched_at,
                expires_at=expires_at,
            )
        )

    def remove_expired_answers(self, now: int) -> None:
        self.session.execute(delete(ReleaseAnswer).where(ReleaseAnswer.expires_at <= now))

    def read_trackers(self) -> list[Tracker]:
        rows = self.session.scalars(select(TrackerRow).order_by(TrackerRow.position))
        return [
            Tracker(
                indexer_id=row.indexer_id,
                name=row.name,
                language=row.language,
                prowlarr_enabled=row.prowlarr_enabled,
                used=row.used,
                auto=row.auto,
            )
            for row in rows
        ]

    def replace_trackers(self, trackers: Iterable[Tracker]) -> None:
        """The trackers, in their order, instead of those saved."""
        self.session.execute(delete(TrackerRow))
        for position, tracker in enumerate(trackers):
            self.session.add(
                TrackerRow(
                    indexer_id=tracker.indexer_id,
                    name=tracker.name,
                    language=tracker.language,
                    prowlarr_enabled=tracker.prowlarr_enabled,
                    used=tracker.used,
                    auto=tracker.auto,
                    position=position,
                )
            )

    def read_rules(self) -> tuple[FilterRule, ...]:
        rows = self.session.scalars(select(FilterRuleRow).order_by(FilterRuleRow.position))
        return tuple(
            FilterRule(
                name=row.name,
                pattern=row.pattern,
                regex=row.regex,
                score=row.score,
                kinds=KINDS.validate_python(tuple(k for k in row.kinds.split(",") if k)),
                enabled=row.enabled,
            )
            for row in rows
        )

    def replace_rules(self, rules: Iterable[FilterRule]) -> None:
        self.session.execute(delete(FilterRuleRow))
        for position, rule in enumerate(rules):
            self.session.add(
                FilterRuleRow(
                    position=position,
                    name=rule.name,
                    pattern=rule.pattern,
                    regex=rule.regex,
                    score=rule.score,
                    kinds=",".join(rule.kinds),
                    enabled=rule.enabled,
                )
            )

    def read_setting(self, key: str) -> object | None:
        """The JSON value of a setting, None when it was never saved."""
        row = self.session.get(Setting, key)
        return None if row is None else json.loads(row.value)

    def save_setting(self, key: str, value: object, now: int, actor: str) -> None:
        self.session.merge(
            Setting(key=key, value=json.dumps(value), updated_at=now, updated_by=actor)
        )

    def add_audit(self, at: int, actor: str, target: str) -> None:
        """A change of the trackers or of the filters, by `actor` (never what changed)."""
        self.session.add(AuditEntry(at=at, actor=actor, action="changed", target=target))

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type RepositoryFactory = Callable[[], ReleaseRepository]


def repository_factory(engine: Engine) -> RepositoryFactory:
    """New repositories on their own session, for the searches that outlive their request; the
    caller closes each."""

    def new() -> ReleaseRepository:
        return ReleaseRepository(Session(engine, expire_on_commit=False))

    return new
