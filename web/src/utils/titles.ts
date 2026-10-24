// Les noms connus d'une œuvre proposés pour un titre : leur langue, leurs sources, triés dans
// l'ordre des langues du réglage `search.language_order`, le nom retenu d'office en tête.

/** Un nom proposé : `language` le code de l'API (« fr », « ja-ro », « latin »...), ses sources de la plus sûre à la moins sûre. */
export type TitleProposal = {
  readonly title: string;
  readonly language: string;
  readonly sources: readonly string[];
};

/** L'ordre des langues par défaut, celui de l'API. */
export const DEFAULT_LANGUAGES: readonly string[] = ["fr", "en", "ja-ro", "latin"];

/** Les codes des langues d'un réglage `search.language_order`, sinon l'ordre par défaut. */
export function languageOrderOf(value: unknown): readonly string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value : DEFAULT_LANGUAGES;
}

/** Les noms une fois chacun (sans casse), leurs sources réunies, triés : `chosen` en tête, puis dans l'ordre des langues. */
export function sortProposals(
  names: readonly TitleProposal[],
  chosen: string,
  languages: readonly string[],
): readonly TitleProposal[] {
  const merged = new Map<string, TitleProposal>();
  for (const name of names) {
    const key = name.title.toLowerCase();
    const known = merged.get(key);
    merged.set(
      key,
      known === undefined
        ? name
        : { ...known, sources: [...known.sources, ...name.sources.filter((s) => !known.sources.includes(s))] },
    );
  }
  const rank = (language: string): number => {
    const index = languages.indexOf(language);
    return index === -1 ? languages.length : index;
  };
  const sorted = [...merged.values()].sort((a, b) => rank(a.language) - rank(b.language));
  const key = chosen.trim().toLowerCase();
  const first = sorted.find((name) => name.title.toLowerCase() === key);
  if (key === "") {
    return sorted;
  }
  return [first ?? { title: chosen.trim(), language: "", sources: [] }, ...sorted.filter((name) => name !== first)];
}

/** Les noms d'une œuvre de la page (`Work.titles`) en propositions. */
export function proposalsOf(
  titles: readonly { readonly title: string; readonly code?: string; readonly sources?: readonly string[] }[],
): readonly TitleProposal[] {
  return titles.map((alt) => ({ title: alt.title, language: alt.code ?? "latin", sources: alt.sources ?? [] }));
}

/** Le premier nom dans l'ordre des langues : le nom retenu d'office quand rien d'autre ne le donne. */
export function firstInOrder(names: readonly TitleProposal[], languages: readonly string[]): string | null {
  return sortProposals(names, "", languages)[0]?.title ?? null;
}
