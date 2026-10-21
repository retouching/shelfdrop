"""The score of a release: the sum of the points of the filter rules its title matches."""

import re
from functools import lru_cache

from shelfdrop.releases.types import FilterRule, RuleMatch
from shelfdrop.works.types import Kind


@lru_cache(maxsize=256)
def compile_rule(pattern: str, regex: bool) -> re.Pattern[str] | None:
    """The expression of a rule, any case; None when it is empty or invalid. Words are whole
    words: neither a letter nor a digit before or after them."""
    if regex:
        source = pattern
    else:
        parts = [word.strip() for word in pattern.split(",") if word.strip()]
        source = "|".join(rf"(?<![^\W_]){re.escape(word)}(?![^\W_])" for word in parts)
    if not source.strip():
        return None
    try:
        return re.compile(source, re.IGNORECASE)
    except re.error:
        return None


def invalid_rules(rules: tuple[FilterRule, ...]) -> list[int]:
    """The positions of the rules whose expression is invalid or empty."""
    return [i for i, rule in enumerate(rules) if compile_rule(rule.pattern, rule.regex) is None]


def score_of(
    title: str, kind: Kind, rules: tuple[FilterRule, ...]
) -> tuple[int, tuple[RuleMatch, ...]]:
    """The score of `title` and the rules that gave it, for a release of `kind`."""
    matches = []
    for rule in rules:
        if not rule.enabled or (rule.kinds and kind not in rule.kinds):
            continue
        pattern = compile_rule(rule.pattern, rule.regex)
        if pattern is not None and pattern.search(title):
            matches.append(RuleMatch(name=rule.name, score=rule.score))
    return sum(match.score for match in matches), tuple(matches)
