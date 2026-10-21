"""Order of the works shown for a search."""

from shelfdrop.utils.isbn import isbn13_of, parse_isbn
from shelfdrop.utils.text import normalize, words
from shelfdrop.works.types import Candidate, Work

MIN_MATCH = 0.25
SIDE_FORMS = frozenset({"novel", "anthology", "doujinshi"})


def name_match(query: str, title: str) -> float:
    """1 for the same name, otherwise the share of words in common (order and accents ignored)."""
    q, t = normalize(query), normalize(title)
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    asked, have = set(q.split()), set(t.split())
    common = len(asked & have)
    if not common:
        return 0.0
    score = common / len(asked | have)
    if t.startswith(q + " ") or q.startswith(t + " "):
        score = max(score, 0.75)
    return score


def best_match(query: str, work: Work) -> float:
    names = [work.title, work.shelf_name, *(n.title for n in work.names)]
    best = max((name_match(query, n) for n in names), default=0.0)
    if work.authors and set(words(query)) <= {w for a in work.authors for w in words(a)}:
        best = max(best, 0.6)  # a search by author
    return best


def score(query: str, work: Work, members: list[Candidate]) -> float:
    isbn = parse_isbn(query)
    if isbn:
        return 2.0 if isbn13_of(isbn) in work.isbns else 0.0
    match = best_match(query, work)
    if match < MIN_MATCH:
        return 0.0
    french = 0.1 if any(n.language == "fr" for n in work.names) else 0.0
    agreement = 0.05 * (len(work.sources) - 1)
    popularity = 0.1 * max((m.popularity for m in members), default=0.0)
    return match + french + agreement + popularity


def rank(
    query: str, merged: list[tuple[Work, list[Candidate]]], *, manga: bool, limit: int = 12
) -> tuple[list[Work], list[Work]]:
    """(works, other forms): for a manga search, novels, anthologies and dōjinshi go apart."""
    scored = [(score(query, work, members), work) for work, members in merged]
    kept = sorted(((s, w) for s, w in scored if s > 0), key=lambda pair: -pair[0])
    main = [w for _, w in kept if not (manga and w.form in SIDE_FORMS)]
    side = [w for _, w in kept if manga and w.form in SIDE_FORMS]
    return main[:limit], side[:limit]
