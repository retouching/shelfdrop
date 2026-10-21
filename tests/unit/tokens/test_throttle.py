"""shelfdrop.tokens.throttle: 60 requests a minute for each token."""

from shelfdrop.tokens.throttle import TOKEN_LIMIT, TokenThrottle


def test_the_61st_request_of_a_minute_waits_for_the_first_to_age() -> None:
    throttle = TokenThrottle()

    allowed = [throttle.allow(1, 1000.0 + i / 10) for i in range(TOKEN_LIMIT)]

    assert all(allowed)
    assert not throttle.allow(1, 1030.0)
    assert throttle.allow(2, 1030.0)
    assert throttle.allow(1, 1060.0)


def test_a_request_refused_is_not_counted() -> None:
    throttle = TokenThrottle()
    for _ in range(TOKEN_LIMIT):
        throttle.allow(1, 1000.0)
    for _ in range(5):
        throttle.allow(1, 1010.0)

    assert throttle.allow(1, 1060.0)
