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

function workOf(read: WorkRead): Work {
  return {
    id: read.id,
    source: read.sources.map((source) => SOURCE_NAMES[source] ?? source).join(", "),
    title: read.shelf_name,
    author: read.authors.join(", "),
    year: read.year,
    volumeCount: read.volumes,
    titles: read.names.map((name) => ({
      title: name.title,
      language: languageLabel(name.language),
      checked: name.checked,
    })),
  };
}

export type FoundWorks = { readonly works: readonly Work[]; readonly unavailable: readonly string[] };

export async function searchWorks(query: string, kind: Kind): Promise<FoundWorks> {
  const params = new URLSearchParams({ q: query, kind });
  const found = await request<WorkSearchRead>("GET", `/v1/works?${params.toString()}`);
  return {
    works: [...found.works, ...found.other_forms].map(workOf),
    unavailable: found.unavailable.map((source) => SOURCE_NAMES[source] ?? source),
  };
}
