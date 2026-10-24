// Recherche d'œuvres : GET /api/v1/works, adaptée au type Work de la page.
import type { Kind, Work } from "../types";
import { request } from "./http";

type NameRead = { readonly title: string; readonly language: string; readonly checked: boolean };

type WorkRead = {
  readonly id: string;
  readonly title: string;
  readonly shelf_name: string;
  readonly authors: readonly string[];
  readonly year: number | null;
  readonly volumes: number | null;
  readonly volumes_fr: number | null;
  readonly names: readonly NameRead[];
  readonly sources: readonly string[];
  readonly cover_url: string | null;
  readonly merge_id: number | null;
  readonly parts: readonly PartRead[];
};

type PartRead = {
  readonly id: string;
  readonly title: string;
  readonly authors: readonly string[];
  readonly sources: readonly string[];
};

type WorkSearchRead = {
  readonly works: readonly WorkRead[];
  readonly other_forms: readonly WorkRead[];
  readonly unavailable: readonly string[];
};

/** Noms propres des sources, tels qu'elles s'écrivent. */
const SOURCE_NAMES: Readonly<Record<string, string>> = {
  mangaupdates: "MangaUpdates",
  kitsu: "Kitsu",
  myanimelist: "MyAnimeList",
  anilist: "AniList",
  mangadex: "MangaDex",
  bnf: "BnF",
  openlibrary: "Open Library",
  wikidata: "Wikidata",
};

/** Code de langue de l'API vers l'étiquette d'une puce : « Romaji », « FR », rien si inconnue. */
export function languageLabel(language: string): string {
  if (language === "ja-ro") {
    return "Romaji";
  }
  return language === "latin" ? "" : language.toUpperCase();
}

function sourcesOf(sources: readonly string[]): string {
  return sources.map((source) => SOURCE_NAMES[source] ?? source).join(", ");
}

/** Une œuvre réunie dans une fusion, telle que la recherche la trouvait seule. */
function partOf(part: PartRead): Work {
  return {
    id: part.id,
    source: sourcesOf(part.sources),
    title: part.title,
    author: part.authors.join(", "),
    year: null,
    volumeCount: null,
    titles: [],
    cover: null,
  };
}

function workOf(read: WorkRead): Work {
  const merged = read.merge_id === null ? {} : { mergeId: read.merge_id, mergedFrom: read.parts.map(partOf) };
  return {
    ...merged,
    id: read.id,
    source: sourcesOf(read.sources),
    title: read.shelf_name,
    author: read.authors.join(", "),
    year: read.year,
    volumeCount: read.volumes,
    cover: read.cover_url === null ? null : `/api/v1/works/cover?id=${encodeURIComponent(read.id)}`,
    titles: read.names.map((name) => ({
      title: name.title,
      language: languageLabel(name.language),
      checked: name.checked,
    })),
  };
}

export type FoundWorks = { readonly works: readonly Work[]; readonly unavailable: readonly string[] };

/** Les œuvres de `query` ; `retry` interroge aussi les sources mises de côté après leurs échecs. */
export async function searchWorks(query: string, kind: Kind, retry = false): Promise<FoundWorks> {
  const params = new URLSearchParams({ q: query, kind });
  if (retry) {
    params.set("retry", "true");
  }
  const found = await request<WorkSearchRead>("GET", `/v1/works?${params.toString()}`);
  return {
    works: [...found.works, ...found.other_forms].map(workOf),
    unavailable: found.unavailable.map((source) => SOURCE_NAMES[source] ?? source),
  };
}

/** Les œuvres réunies en une sous le nom choisi ; une fusion parmi elles reçoit les autres. */
export async function mergeWorks(kind: Kind, workIds: readonly string[], shelfName: string): Promise<void> {
  await request<unknown>("POST", "/v1/works/merges", { kind, work_ids: workIds, shelf_name: shelfName });
}

export async function splitWorks(mergeId: number): Promise<void> {
  await request<unknown>("DELETE", `/v1/works/merges/${String(mergeId)}`);
}
