"""What every route shares about the request session: its release after the response."""

from collections.abc import Iterator

from sqlalchemy.orm import Session
from wireup import Injected
from wireup.integration.fastapi import inject


@inject
def release_session(session: Injected[Session]) -> Iterator[None]:
    """Close the request session in the threadpool once the response is sent.

    build_app() registers it on the whole application. Without it the wireup scope would close
    the session on the event loop thread, where a ROLLBACK blocks every other request.
    """
    try:
        yield
    finally:
        session.close()
