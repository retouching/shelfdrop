"""PlacementWorker: the rounds of the placement and of the files of Ranger, every 30 seconds,
until stopped (the command `shelfdrop placement run`, the service `placement` of Compose)."""

import logging

import anyio

from shelfdrop.placement.byhand import HandPlacement
from shelfdrop.placement.service import PlacementService
from shelfdrop.placement.types import PlacementOptions

logger = logging.getLogger(__name__)


class PlacementWorker:
    def __init__(
        self, service: PlacementService, hand: HandPlacement, options: PlacementOptions
    ) -> None:
        self.service = service
        self.hand = hand
        self.options = options

    async def run(self) -> None:
        """Until cancelled: a round that fails is logged, and the next one comes."""
        logger.info("Placement worker started")
        while True:
            try:
                await self.service.round()
            except Exception:
                logger.exception("Placement round failed")
            try:
                await self.hand.round()
            except Exception:
                logger.exception("Round of Ranger failed")
            await anyio.sleep(self.options.every_seconds)
