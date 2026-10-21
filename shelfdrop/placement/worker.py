"""PlacementWorker: the rounds of the placement, every 30 seconds, until stopped (the command
`shelfdrop placement run`, the service `placement` of Compose)."""

import logging

import anyio

from shelfdrop.placement.service import PlacementService
from shelfdrop.placement.types import PlacementOptions

logger = logging.getLogger(__name__)


class PlacementWorker:
    def __init__(self, service: PlacementService, options: PlacementOptions) -> None:
        self.service = service
        self.options = options

    async def run(self) -> None:
        """Until cancelled: a round that fails is logged, and the next one comes."""
        logger.info("Placement worker started")
        while True:
            try:
                await self.service.round()
            except Exception:
                logger.exception("Placement round failed")
            await anyio.sleep(self.options.every_seconds)
