"""shelfdrop.auth.throttle: 5 attempts a minute from one address, 30 an hour in all."""

from shelfdrop.auth.throttle import LoginThrottle


def test_five_attempts_a_minute_from_one_address() -> None:
    throttle = LoginThrottle()

    allowed = [throttle.allow("10.0.0.1", 1000 + i) for i in range(6)]

    assert allowed == [True] * 5 + [False]
    assert throttle.allow("10.0.0.2", 1006)
    assert throttle.allow("10.0.0.1", 1060)


def test_thirty_attempts_an_hour_in_all() -> None:
    throttle = LoginThrottle()

    allowed = [throttle.allow(f"10.0.0.{i}", 1000 + i) for i in range(31)]

    assert allowed == [True] * 30 + [False]
    assert throttle.allow("10.0.1.1", 1000 + 3600)


def test_a_refused_attempt_is_not_counted() -> None:
    throttle = LoginThrottle()
    for i in range(7):
        throttle.allow("10.0.0.1", 1000 + i)

    assert throttle.allow("10.0.0.1", 1060)
