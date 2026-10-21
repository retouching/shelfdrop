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
};

export function SearchForm({ kind, initialQuery, busy, onSearch }: Props): ReactElement {
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
    <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-surface p-5">
      <div className="flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label={texts.search.kindLabel} className="inline-flex rounded-lg bg-slate-100 p-1">
          {kinds.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={option === kind}
              onClick={() => {
                onSearch(query.trim(), option);
              }}
              className={
                option === kind
                  ? "rounded-md bg-surface px-4 py-1.5 text-sm font-medium text-ink shadow-sm"
                  : "rounded-md px-4 py-1.5 text-sm text-slate-500 hover:text-ink"
              }
            >
              {texts.kinds[option]}
            </button>
          ))}
        </div>
        <div className="relative min-w-64 flex-1">
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
          className="hover:bg-accent-strong-strong flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white disabled:cursor-wait disabled:opacity-80"
        >
          {busy ? <Spinner /> : null}
          {busy ? texts.loading.searching : texts.search.submit}
        </button>
      </div>
      {error === null ? null : (
        <p id="query-error" role="alert" className="mt-3 text-sm text-rose-600">
          {error}
        </p>
      )}
    </form>
  );
}
