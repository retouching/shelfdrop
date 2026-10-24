import type { Kind } from "../types";

/** Les sections de la page ; chacune a son adresse. */
export type Page = "auto" | "manual" | "waiting" | "downloads" | "place" | "metadata" | "settings";

/** L'adresse de chaque section, celle de ses liens dans la barre. */
export const pagePaths = {
  auto: "/",
  manual: "/manual",
  waiting: "/waiting",
  downloads: "/downloads",
  place: "/place",
  metadata: "/jellyfin",
  settings: "/settings",
} as const satisfies Readonly<Record<Page, string>>;

/** Les onglets de Paramètres, dans leur ordre ; le premier est `/settings` seul. */
export const settingsTabs = [
  "services",
  "sources",
  "search",
  "filters",
  "placement",
  "discord",
  "access",
  "logs",
] as const;

export type SettingsTab = (typeof settingsTabs)[number];

/** L'onglet d'un segment d'adresse ; null pour un segment inconnu. */
export function settingsTabOf(slug: string | undefined): SettingsTab | null {
  return settingsTabs.find((tab) => tab === slug) ?? null;
}

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

/** Le type cherché par défaut, jamais écrit dans l'adresse sans texte. */
export const defaultKind: Kind = "manga";

/**
 * Les paramètres d'une recherche : `/?q=…&kind=…&work=…`, `/manual?q=…&kind=…`. Lus, chacun est
 * présent, `undefined` s'il manque ou ne vaut rien : TanStack Router garde sinon la valeur brute
 * de l'adresse à côté de celles vérifiées.
 */
export type SearchParams = {
  readonly q?: string | undefined;
  readonly kind?: Kind | undefined;
  /** L'œuvre choisie dans la liste (page Automatique seule). */
  readonly work?: string | undefined;
};

function text(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

/** Les paramètres lus dans l'adresse ; une valeur invalide est ignorée. */
export function searchParamsOf(raw: Readonly<Record<string, unknown>>, withWork: boolean): SearchParams {
  const q = text(raw["q"]);
  const kind = kinds.find((option) => option === raw["kind"]);
  const work = q === undefined || !withWork ? undefined : text(raw["work"]);
  return { q, kind, work };
}

/** Les paramètres écrits pour une recherche : le type par défaut n'apparaît qu'avec un texte. */
export function searchParamsFor(q: string, kind: Kind, work?: string): SearchParams {
  const query = q.trim();
  return {
    ...(query === "" ? {} : { q: query }),
    ...(query === "" && kind === defaultKind ? {} : { kind }),
    ...(query === "" || work === undefined ? {} : { work }),
  };
}

export const placeFilters = ["todo", "ignored", "all"] as const;

export type PlaceFilter = (typeof placeFilters)[number];

/** Les filtres de Ranger : `/place?q=…&filter=…` ; « À ranger » est le filtre sans paramètre. */
export type PlaceParams = {
  readonly q?: string | undefined;
  readonly filter?: Exclude<PlaceFilter, "todo"> | undefined;
};

export function placeParamsOf(raw: Readonly<Record<string, unknown>>): PlaceParams {
  const q = text(raw["q"]);
  const filter = placeFilters.find((option) => option === raw["filter"]);
  return { q, filter: filter === "todo" ? undefined : filter };
}

/** Les paramètres d'une adresse, en texte simple (`?q=one+piece`), jamais en JSON. */
export function parseSearch(search: string): Record<string, string> {
  return Object.fromEntries(new URLSearchParams(search));
}

export function stringifySearch(params: Readonly<Record<string, unknown>>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string" && value !== "") {
      query.set(key, value);
    }
  }
  const written = query.toString();
  return written === "" ? "" : `?${written}`;
}
