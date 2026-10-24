"""Merge the candidates of every source into works, and choose the names of each work."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from shelfdrop.utils.text import compact, is_latin, normalize, words
from shelfdrop.works.names import is_abbreviation, language_of, match_key
from shelfdrop.works.types import (
    Candidate,
    Form,
    Name,
    NameChoice,
    SourceName,
    Work,
    WorkMerge,
    WorkPart,
)

# Most trusted first, for the title, the authors, the form and the year.
PRIORITY: tuple[SourceName, ...] = (
    "myanimelist",
    "anilist",
    "mangaupdates",
    "kitsu",
    "mangadex",
    "openlibrary",
    "wikidata",
    "bnf",
)
COVER_PRIORITY: tuple[SourceName, ...] = (
    "openlibrary",
    "mangaupdates",
    "kitsu",
    "myanimelist",
    "anilist",
)
# The sources that list a work once: two of their entries are two works. The others may list
# it several times: the BnF a record per run of volumes, MangaDex its colored edition,
# Wikidata an item per edition.
ONE_ENTRY: frozenset[SourceName] = frozenset({"myanimelist", "anilist", "mangaupdates", "kitsu"})
# The languages of the names searched by default, in their order; "release" is a name as the
# releases write it. A name in another language, or in none known ("latin"), stays unchecked.
LANGUAGE_ORDER = {"fr": 0, "en": 1, "ja-ro": 2, "release": 3}
MAX_CHECKED = 6


def rank_of(source: SourceName) -> int:
    return PRIORITY.index(source)


def keys_of(candidate: Candidate) -> Iterable[str]:
    yield f"{candidate.source}:{candidate.source_id}"
    for source, external_id in candidate.external_ids.items():
        yield f"{source}:{external_id}"
    for isbn in candidate.isbns:
        yield f"isbn:{isbn}"


def match_names(candidate: Candidate) -> set[str]:
    """Names precise enough to say two candidates are the same work."""
    found = set()
    for name in (Name(title=candidate.title, language="latin"), *candidate.names):
        if is_abbreviation(name.title):
            continue
        key = match_key(name.title)
        if len(key) >= 4:
            found.add(key)
    return found


def author_words(members: Iterable[Candidate]) -> set[str]:
    return {
        w for member in members for author in member.authors for w in words(author) if len(w) >= 3
    }


def consonants(word: str) -> str:
    """'meibii' and 'maybe' to 'mb': a word without its vowels nor its doubled letters."""
    kept = [c for c in word if c not in "aeiouy"]
    return "".join(c for i, c in enumerate(kept) if i == 0 or kept[i - 1] != c)


def author_sounds(members: Iterable[Candidate]) -> set[str]:
    """Each author as the consonants of its words, in any order: the romanizations of a
    Japanese name differ by their vowels ("Maybe", "Meibii"; "Yuu", "Yu")."""
    found = set()
    for member in members:
        for author in member.authors:
            sound = " ".join(sorted(c for c in map(consonants, words(author)) if c))
            if sound:
                found.add(sound)
    return found


def same_authors(a: list[Candidate], b: list[Candidate]) -> bool:
    """Any word of 3 letters or more in common (sources disagree on the order of Japanese
    names: "Akasaka Aka", "Aka Akasaka"), or a whole name with the same consonants."""
    return bool(author_words(a) & author_words(b) or author_sounds(a) & author_sounds(b))


def title_keys(members: Iterable[Candidate]) -> set[str]:
    """The names of a group that are the title of one of its members, not another name."""
    return {
        match_key(m.title)
        for m in members
        if not is_abbreviation(m.title) and len(match_key(m.title)) >= 4
    }


def name_keys(members: Iterable[Candidate]) -> set[str]:
    return {key for member in members for key in match_names(member)}


def one_entry_sources(members: Iterable[Candidate]) -> set[SourceName]:
    return {m.source for m in members if m.source in ONE_ENTRY}


def same_work(a: list[Candidate], b: list[Candidate]) -> bool:
    """Whether two groups of candidates may be the same work by their names."""
    if not name_keys(a) & name_keys(b):
        return False
    if one_entry_sources(a) & one_entry_sources(b):
        return False
    if author_words(a) and author_words(b) and not same_authors(a, b):
        return False
    # The BnF dates the French edition, often years after the original: its year proves nothing.
    years_a = [m.year for m in a if m.year and m.source != "bnf"]
    years_b = [m.year for m in b if m.year and m.source != "bnf"]
    if not years_a or not years_b:
        return True
    return max(min(years_a), min(years_b)) - min(max(years_a), max(years_b)) <= 2


def strength(a: list[Candidate], b: list[Candidate]) -> int:
    """0 when the two groups share a name that is a title on both sides, 1 on one side, 2 when
    the name they share is another name on both sides: the stronger pairs are joined first."""
    shared = name_keys(a) & name_keys(b)
    titles_a, titles_b = title_keys(a), title_keys(b)
    if shared & titles_a & titles_b:
        return 0
    return 1 if shared & (titles_a | titles_b) else 2


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        self.parent[self.find(a)] = self.find(b)


def by_keys(candidates: list[Candidate]) -> list[list[int]]:
    """The indexes of the candidates that share an id, an id at another source or an ISBN,
    together, in the order of their first member."""
    sets = UnionFind(len(candidates))
    owner: dict[str, int] = {}
    for i, candidate in enumerate(candidates):
        for key in keys_of(candidate):
            if key in owner:
                sets.union(i, owner[key])
            else:
                owner[key] = i
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(candidates)):
        groups[sets.find(i)].append(i)
    return list(groups.values())


def group(candidates: list[Candidate]) -> list[list[Candidate]]:
    """Candidates of the same work together: shared id or ISBN first, then same name, group
    against group, so that one record cannot chain several works.

    The groups with authors join by name the strongest pairs first (`strength`), each join
    checked again on the groups joined so far. A group without any author (the Kitsu client
    reads none, some records of the BnF have none) then joins another only when it is the one
    group with authors it may be (or, with none possible, the one group without); when several
    are possible, it stays alone.
    """
    members = dict(enumerate(by_keys(candidates)))
    first = {i: [candidates[k] for k in indexes] for i, indexes in members.items()}

    def of(root: int) -> list[Candidate]:
        return [candidates[k] for k in members[root]]

    root_of = {i: i for i in members}

    def find(i: int) -> int:
        while root_of[i] != i:
            i = root_of[i]
        return i

    def join(a: int, b: int) -> None:
        kept, gone = min(a, b), max(a, b)
        members[kept] = sorted(members[kept] + members.pop(gone))
        root_of[gone] = kept

    authored = [i for i, g in first.items() if author_words(g)]
    pairs = sorted(
        (strength(first[i], first[j]), i, j)
        for n, i in enumerate(authored)
        for j in authored[n + 1 :]
        if name_keys(first[i]) & name_keys(first[j])
    )
    for _, i, j in pairs:
        a, b = find(i), find(j)
        if a != b and same_work(of(a), of(b)):
            join(a, b)
    joining = True
    while joining:
        joining = False
        for root in sorted(members):
            if author_words(of(root)):
                continue
            possible = [o for o in sorted(members) if o != root and same_work(of(root), of(o))]
            # The groups without authors may be any of the others: they count only when no
            # group with authors is possible.
            possible = [o for o in possible if author_words(of(o))] or possible
            if len(possible) == 1:
                join(root, possible[0])
                joining = True
                break
    return [sorted(of(root), key=lambda c: rank_of(c.source)) for root in sorted(members)]


@dataclass(frozen=True)
class MergedName:
    """A name of a merged work: its best casing, its language, whether a French edition was
    published under it (BnF), and whether its language was guessed rather than given."""

    title: str
    language: str
    published: bool
    guessed: bool


def names_of(members: list[Candidate]) -> list[MergedName]:
    """Every name once, with the most precise language known, the best casing, and whether a
    French edition was published under it (BnF).

    The BnF writes titles in catalogue case ("Dusk maiden of amnesia"): when another source has
    the same name, its casing wins, but the name stays French. A name no source gave a language
    for gets the one its letters and its words tell (`language_of`), if any.
    """
    by_key: dict[str, tuple[str, str, int, bool]] = {}
    for member in members:
        for name in (Name(title=member.title, language="latin"), *member.names):
            key = match_key(name.title) or name.title
            casing_rank = 1 if member.source == "bnf" else 0
            published = member.source == "bnf"
            current = by_key.get(key)
            if current is None:
                by_key[key] = (name.title, name.language, casing_rank, published)
                continue
            title, language, rank, was_published = current
            if casing_rank < rank:
                title, rank = name.title, casing_rank
            if language == "latin" or (name.language == "fr" and language != "fr"):
                language = name.language if name.language != "latin" else language
            by_key[key] = (title, language, rank, was_published or published)
    return [
        MergedName(
            title=title,
            language=language_of(title) if language == "latin" else language,
            published=published,
            guessed=language == "latin",
        )
        for title, language, _, published in by_key.values()
    ]


def choices(names: list[MergedName], title: str) -> list[NameChoice]:
    """The names searched by default: French, English, romaji, the languages a source gave
    before the guessed ones, at most MAX_CHECKED; and the title of the work itself whatever its
    language, so that a work always has one. A name in another language, or in none known,
    stays unchecked."""
    title_key = match_key(title)

    def searchable(name: MergedName) -> bool:
        known = name.language in LANGUAGE_ORDER or match_key(name.title) == title_key
        return is_latin(name.title) and not is_abbreviation(name.title) and known

    def order(name: MergedName) -> tuple[int, bool, bool, int]:
        rank = LANGUAGE_ORDER.get(name.language, 9 if match_key(name.title) != title_key else 8)
        return (rank, name.guessed, not name.published, len(name.title))

    checked_keys: list[str] = []
    checked_compact: set[str] = set()
    found = []
    for name in sorted(names, key=order):
        key = normalize(name.title)
        # "Chainsaw Man: Public Safety Saga" is a part of "Chainsaw Man", and "Chainsawman" the
        # same search as "Chainsaw Man": neither is searched by default.
        is_part = any(key.startswith(k + " ") for k in checked_keys)
        checked = (
            searchable(name)
            and not is_part
            and compact(name.title) not in checked_compact
            and len(checked_keys) < MAX_CHECKED
        )
        if checked:
            checked_keys.append(key)
            checked_compact.add(compact(name.title))
        found.append(NameChoice(title=name.title, language=name.language, checked=checked))
    return sorted(found, key=lambda c: not c.checked)


def shelf_name(names: list[MergedName], fallback: str) -> str:
    """The title of the French edition (BnF) first, then any French name, English, romaji, as
    the sources gave them; a name whose language was guessed comes after."""
    for name in names:
        if name.published and name.language == "fr" and not is_abbreviation(name.title):
            return name.title
    for guessed in (False, True):
        for wanted in ("fr", "en", "ja-ro", "latin"):
            for name in names:
                wanted_name = name.guessed == guessed and name.language == wanted
                if wanted_name and not is_abbreviation(name.title):
                    return name.title
    return fallback


def form_of(members: list[Candidate]) -> Form:
    for member in members:
        if member.form != "other":
            return member.form
    return "other"


def build_work(members: list[Candidate]) -> Work:
    best = members[0]
    names = names_of(members)
    authors = next((list(m.authors) for m in members if m.authors), [])
    years = [m.year for m in members if m.year and m.source != "bnf"] or [
        m.year for m in members if m.year
    ]
    by_source = {m.source: m for m in members}
    mangaupdates = by_source.get("mangaupdates")
    volumes = (mangaupdates.volumes if mangaupdates else None) or max(
        (m.volumes for m in members if m.volumes), default=None
    )
    cover = next(
        (
            by_source[s].cover_url
            for s in COVER_PRIORITY
            if s in by_source and by_source[s].cover_url
        ),
        None,
    )
    title = best.title
    if is_abbreviation(title) or not is_latin(title):
        title = next(
            (n.title for n in names if n.language == "en" and not is_abbreviation(n.title)), title
        )
    return Work(
        id=f"{best.source}:{best.source_id}",
        title=title,
        shelf_name=shelf_name(names, best.title),
        authors=tuple(authors),
        year=min(years) if years else None,
        volumes=volumes,
        volumes_fr=max((m.volumes_fr for m in members if m.volumes_fr), default=None),
        form=form_of(members),
        names=tuple(choices(names, title)),
        sources=tuple(sorted({m.source for m in members}, key=rank_of)),
        cover_url=cover,
        isbns=tuple(sorted({i for m in members for i in m.isbns})),
        links={m.source: m.url for m in members if m.url},
        covers={m.source: m.cover_url for m in members if m.cover_url},
        summaries={m.source: m.summary for m in members if m.summary},
        keys=tuple(f"{m.source}:{m.source_id}" for m in members),
    )


def merge(candidates: list[Candidate]) -> list[tuple[Work, list[Candidate]]]:
    return [(build_work(members), members) for members in group(candidates)]


def part_of(work: Work) -> WorkPart:
    return WorkPart(id=work.id, title=work.shelf_name, authors=work.authors, sources=work.sources)


def join_merges(
    merged: list[tuple[Work, list[Candidate]]], merges: Sequence[WorkMerge]
) -> list[tuple[Work, list[Candidate]]]:
    """The works a merge by hand joins made one, in the place of the first of them: built again
    from all their members, under the name on the shelf chosen. A merge whose works the search
    found one of, or none, changes nothing."""
    owner = {key: m for m in merges for key in m.keys}
    joined: dict[int, list[int]] = defaultdict(list)
    for index, (work, _) in enumerate(merged):
        found = next((owner[key] for key in work.keys if key in owner), None)
        if found is not None:
            joined[found.id].append(index)
    by_id = {m.id: m for m in merges}
    first: dict[int, tuple[Work, list[Candidate]]] = {}
    gone: set[int] = set()
    for merge_id, indexes in joined.items():
        if len(indexes) < 2:
            continue
        works = [merged[i][0] for i in indexes]
        members = [c for i in indexes for c in merged[i][1]]
        built = replace(
            build_work(members),
            shelf_name=by_id[merge_id].shelf_name,
            merge_id=merge_id,
            parts=tuple(part_of(w) for w in works),
        )
        first[indexes[0]] = (built, members)
        gone.update(indexes[1:])
    return [first.get(i, pair) for i, pair in enumerate(merged) if i not in gone]


# The BnF is asked again for the best works it did not find, at most this many times.
FRENCH_EDITION_QUERIES = 3
# The language of the name the BnF is asked under, by preference: a French edition goes by a
# French name, else often by the romaji one ("Gunnm"), else the English one.
FRENCH_EDITION_LANGUAGES = ("fr", "ja-ro", "en")


def french_edition_names(works: list[Work], asked: str) -> list[str]:
    """The names to ask the BnF again under, one for each of the best works it did not find:
    the first name searched by default in FRENCH_EDITION_LANGUAGES, but the text already asked
    ("Battle Angel Alita" finds Gunnm, whose name finds its French edition)."""
    asked_key = match_key(asked)
    found: list[str] = []
    for work in works[:FRENCH_EDITION_QUERIES]:
        if "bnf" in work.sources:
            continue
        for language in FRENCH_EDITION_LANGUAGES:
            name = next(
                (
                    n.title
                    for n in work.names
                    if n.checked
                    and n.language == language
                    and match_key(n.title) != asked_key
                    and all(match_key(f) != match_key(n.title) for f in found)
                ),
                None,
            )
            if name is not None:
                found.append(name)
                break
    return found
