"""The routes of the filters of the releases: rules with points, and a minimum score. Async, as
every route of the release search (ADR 0011)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_session
from shelfdrop.modules.filters.errors import invalid_filter_rule
from shelfdrop.modules.filters.schemas import FilterRuleBody, FiltersBody
from shelfdrop.releases.exceptions import InvalidRuleError
from shelfdrop.releases.service import ReleaseService
from shelfdrop.releases.types import FilterRule, Filters

router = APIRouter(prefix="/v1/filters", tags=["filters"], route_class=WireupRoute)


def filters_body(filters: Filters) -> FiltersBody:
    return FiltersBody(
        rules=[FilterRuleBody.model_validate(rule) for rule in filters.rules],
        minimum=filters.minimum,
    )


@router.get("")
async def read_filters(service: Injected[ReleaseService]) -> FiltersBody:
    return filters_body(await service.read_filters())


@router.put("")
async def save_filters(
    service: Injected[ReleaseService],
    account: Annotated[Account, Depends(require_session)],
    body: FiltersBody,
) -> FiltersBody:
    filters = Filters(
        rules=tuple(
            FilterRule(
                name=rule.name,
                pattern=rule.pattern,
                regex=rule.regex,
                score=rule.score,
                kinds=tuple(dict.fromkeys(rule.kinds)),
                enabled=rule.enabled,
            )
            for rule in body.rules
        ),
        minimum=body.minimum,
    )
    try:
        return filters_body(await service.save_filters(filters, account.username))
    except InvalidRuleError as exc:
        raise invalid_filter_rule(exc.positions) from exc
