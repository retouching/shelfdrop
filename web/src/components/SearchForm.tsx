import { useState, type ReactElement, type SubmitEvent } from "react";

import { texts } from "../texts";
import type { Kind } from "../types";
import { SearchIcon } from "./icons";
import { Spinner } from "./Skeletons";

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

type Props = {
  readonly kind: Kind;
  readonly initialQuery: string;
  readonly busy: boolean;
  readonly onSearch: (query: string, kind: Kind) => void;
  /** Le type choisi sans texte de recherche : aucune recherche ne part. */
  readonly onKind: (kind: Kind) => void;
  /** Tout effacer : le texte, l'œuvre choisie, les releases et la sélection. */
  readonly onClear: () => void;
  /** Une recherche est affichée (texte envoyé ou résultats) : le bouton Effacer apparaît. */
  readonly searched: boolean;
};

export function SearchForm({ kind, initialQuery, busy, onSearch, onKind, onClear, searched }: Props): ReactElement {
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (query.trim().length < 2) {
      setError(texts.search.tooShort);
      return;
    }
    setError(null);
    onSearch(query.trim(), kind);
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-surface p-4 md:p-5">
      <div className="flex flex-wrap items-center gap-3">
        <div
          role="radiogroup"
          aria-label={texts.search.kindLabel}
          className="flex w-full rounded-lg bg-slate-100 p-1 sm:inline-flex sm:w-auto"
        >
          {kinds.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={option === kind}
              onClick={() => {
                // Sans texte assez long, le type change sans lancer de recherche.
                if (query.trim().length < 2) {
                  onKind(option);
                } else {
                  onSearch(query.trim(), option);
                }
              }}
              className={
                option === kind
                  ? "flex-1 rounded-md bg-surface px-4 py-1.5 text-sm font-medium text-ink shadow-sm sm:flex-none"
                  : "flex-1 rounded-md px-4 py-1.5 text-sm text-slate-500 hover:text-ink sm:flex-none"
              }
            >
              {texts.kinds[option]}
            </button>
          ))}
        </div>
        <div className="relative min-w-0 flex-1 basis-full sm:min-w-64 sm:basis-0">
          <label className="sr-only" htmlFor="query">
            {texts.search.label}
          </label>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            id="query"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            placeholder={texts.search.placeholder}
            aria-invalid={error !== null}
            aria-describedby={error === null ? undefined : "query-error"}
            className="w-full rounded-lg border border-slate-200 bg-surface py-2 pr-3 pl-9 text-ink outline-none placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-accent-ring"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-80 sm:flex-none"
        >
          {busy ? <Spinner /> : null}
          {busy ? texts.loading.searching : texts.search.submit}
        </button>
        {searched || query !== "" ? (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setError(null);
              onClear();
            }}
            className="flex-1 rounded-lg border border-slate-200 bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-slate-100 sm:flex-none"
          >
            {texts.search.clear}
          </button>
        ) : null}
      </div>
      {error === null ? null : (
        <p id="query-error" role="alert" className="mt-3 text-sm text-rose-600">
          {error}
        </p>
      )}
    </form>
  );
}
