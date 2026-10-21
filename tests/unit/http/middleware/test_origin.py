"""shelfdrop.http.middleware.origin: a write names the host of the request as its origin."""

import pytest

from shelfdrop.http.middleware.origin import same_host


@pytest.mark.parametrize(
    ("origin", "host", "same"),
    [
        ("https://shelfdrop.maigo.party", "shelfdrop.maigo.party", True),
        ("http://127.0.0.1:8000", "127.0.0.1:8000", True),
        ("https://Shelfdrop.Maigo.Party", "shelfdrop.maigo.party", True),
        ("https://shelfdrop.maigo.party", "evil.example", False),
        ("https://shelfdrop.maigo.party.evil.example", "shelfdrop.maigo.party", False),
        ("http://127.0.0.1:8001", "127.0.0.1:8000", False),
        ("null", "shelfdrop.maigo.party", False),
        (None, "shelfdrop.maigo.party", False),
        ("https://shelfdrop.maigo.party", None, False),
        ("file://shelfdrop.maigo.party", "shelfdrop.maigo.party", False),
    ],
)
def test_same_host(origin: str | None, host: str | None, same: bool) -> None:
    assert same_host(origin, host) is same
