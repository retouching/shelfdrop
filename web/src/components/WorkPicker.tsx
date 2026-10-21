import { useEffect, useState, type KeyboardEvent, type ReactElement } from "react";

import { mockWorks } from "../mock/data";
import { wait } from "../mock/latency";
import { texts } from "../texts";
import type { Kind, Work } from "../types";
import { CheckIcon, SearchIcon } from "./icons";
import { Bone, LoadingLabel } from "./Skeletons";

export const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

/** Œuvre choisie et nom gardé dans la bibliothèque (un de ses titres). */
export type Pick = {
  readonly work: Work;
  readonly shelfName: string;
};

function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function words(text: string): readonly string[] {
  return normalize(text)
    .split(/[^\p{L}\p{N}]+/u)
    .filter((word) => word.length > 1);
}

/** Maquette : cherche dans les œuvres fictives, sur tous leurs noms et l'auteur. */
function findWorks(kind: Kind, query: string): readonly Work[] {
  const asked = new Set(words(query));
  // Un livre et son livre audio sont la même œuvre : les deux listes servent aux deux types.
  const pool = kind === "manga" ? mockWorks.manga : [...mockWorks.ebook, ...mockWorks.audiobook];
  if (asked.size === 0) {
    return pool;
  }
  const covered = (text: string): boolean => {
    const needed = words(text);
    return needed.length > 0 && needed.every((word) => asked.has(word));
  };
  return pool.filter((work) => covered(work.author) || work.titles.some((alt) => covered(alt.title)));
}

/** Nom de fichier ou de release → texte de recherche : sans extension, année, tags ni numéro de tome. */
export function guessQuery(name: string): string {
  return name
    .replace(/\.(epub|pdf|cbz|cbr|m4b|mp3|zip)$/iu, "")
    .replace(/[._]/gu, " ")
    .replace(/\[[^\]]*\]/gu, " ")
    .replace(/\b(19|20)\d{2}\b/gu, " ")
    .replace(/\b(french|fr|vf|multi|epub|pdf|cbz|cbr|m4b|mp3|nogrp|notag|integrale)\b.*$/giu, " ")
    .replace(/\s+-?\s*(T|tome|ch|chap|chapitre)\.?\s*\d.*$/iu, "")
    .replace(/\s+/gu, " ")
    .trim();
}

/** Nom pris par défaut : le titre français, sinon celui qui a trouvé l'œuvre, sinon le titre d'origine. */
function defaultName(work: Work, query: string): string {
  const asked = new Set(words(query));
  const french = work.titles.find((alt) => alt.language === "FR");
  const matched = work.titles.find((alt) => words(alt.title).every((word) => asked.has(word)));
  return (french ?? matched ?? work.titles[0])?.title ?? work.title;
}

type Props = {
  readonly kind: Kind;
  readonly initialQuery: string;
  readonly value: Pick | null;
  readonly onChange: (pick: Pick | null) => void;
  /** Œuvres à ne pas proposer (celles qu'on fusionne). */
  readonly exclude?: ReadonlySet<string>;
  /** Choix multiple : les œuvres cochées, et le changement d'une case. */
  readonly picked?: ReadonlySet<string>;
  readonly onToggle?: (work: Work) => void;
  /** Choix du nom dans la bibliothèque sous la liste. */
  readonly withName?: boolean;
};

/** Recherche d'œuvre dans les API de livres, utilisée pour associer un fichier ou une release. */
export function WorkPicker({
  kind,
  initialQuery,
  value,
  onChange,
  exclude,
  withName = true,
  picked,
  onToggle,
}: Props): ReactElement {
  const [query, setQuery] = useState(initialQuery);
  const [submitted, setSubmitted] = useState(initialQuery);
  const [doneKey, setDoneKey] = useState<string | null>(null);
  const key = `${kind}|${submitted}`;
  const searching = doneKey !== key;

  useEffect(() => {
    let cancelled = false;
    void wait(700).then(() => {
      if (!cancelled) {
        setDoneKey(key);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [key]);

  const works = searching ? [] : findWorks(kind, submitted).filter((candidate) => exclude?.has(candidate.id) !== true);

  // Pas de <form> ici : le sélecteur vit aussi dans le formulaire d'envoi, et les formulaires ne s'imbriquent pas.
  function search(): void {
    onChange(null);
    setSubmitted(query);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Enter") {
      event.preventDefault();
      search();
    }
  }

  return (
    <div className="space-y-3">
      <div role="search" className="flex items-end gap-2">
        <label className="flex-1 space-y-1.5">
          <span className="text-sm font-medium">{texts.place.workSearch}</span>
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            onKeyDown={onKeyDown}
            placeholder={texts.place.workSearchPlaceholder}
            className={field}
          />
        </label>
        <button
          type="button"
          onClick={search}
          aria-label={texts.search.submit}
          className="rounded-lg border border-slate-200 p-2.5 text-slate-600 hover:bg-slate-50 hover:text-ink"
        >
          <SearchIcon />
        </button>
      </div>

      <div aria-busy={searching} className="max-h-56 overflow-y-auto">
        {searching ? (
          <>
            <LoadingLabel label={texts.loading.works} />
            <ul aria-hidden="true" className="space-y-2">
              {[0, 1].map((i) => (
                <li key={i} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
                  <Bone className="h-12 w-9 rounded" />
                  <span className="flex-1 space-y-2">
                    <Bone className="h-3.5 w-1/2" />
                    <Bone className="h-3 w-1/3" />
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : works.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
            {texts.works.none(submitted)}
          </p>
        ) : (
          <ul className="space-y-2">
            {works.map((candidate) => {
              const active = picked === undefined ? candidate.id === value?.work.id : picked.has(candidate.id);
              return (
                <li key={candidate.id}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      if (onToggle === undefined) {
                        onChange({ work: candidate, shelfName: defaultName(candidate, submitted) });
                      } else {
                        onToggle(candidate);
                      }
                    }}
                    className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left ${
                      active ? "border-accent ring-2 ring-accent-ring" : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className="flex h-12 w-9 items-center justify-center rounded bg-accent-soft text-xs font-semibold text-accent-text"
                    >
                      {candidate.title.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{candidate.title}</span>
                      <span className="block truncate text-sm text-slate-500">
                        {candidate.author} · {candidate.year} ·{" "}
                        {candidate.titles
                          .slice(1, 3)
                          .map((alt) => alt.title)
                          .join(", ")}
                      </span>
                    </span>
                    {active ? <CheckIcon className="size-5 text-accent-text" /> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {value === null || !withName ? null : (
        <label className="block space-y-1.5">
          <span className="text-sm font-medium">{texts.place.shelfName}</span>
          <select
            value={value.shelfName}
            onChange={(event) => {
              onChange({ ...value, shelfName: event.target.value });
            }}
            className={field}
          >
            {value.work.titles.map((alt) => (
              <option key={alt.title} value={alt.title}>
                {alt.title} ({alt.language})
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
