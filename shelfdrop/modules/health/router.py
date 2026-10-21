"""GET /health: a liveness probe without I/O (ADR 0009); never authenticated."""

from fastapi import APIRouter
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.health.schemas import HealthStatus

router = APIRouter(route_class=WireupRoute)


@router.get("/health")
def health() -> HealthStatus:
    """200 as soon as the application serves requests; no database, Redis or other I/O."""
    return HealthStatus(status="ok")
