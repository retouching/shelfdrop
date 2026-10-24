import type { ReactElement } from "react";

import { texts } from "../texts";
import type { Work } from "../types";
import { CheckIcon, MergeIcon } from "./icons";
import { Spinner } from "./Skeletons";

type Props = {
  readonly query: string;
  readonly works: readonly Work[];
  readonly selectedId: string | null;
  readonly loading: boolean;
  readonly onChoose: (work: Work) => void;
  readonly onMerge: (work: Work) => void;
  readonly onSplit: (work: Work) => void;
};

function initials(title: string): string {
  return title
    .split(/\s+/u)
    .filter((word) => /^\p{L}/u.test(word))
    .slice(0, 2)
    .map((word) => word.slice(0, 1).toUpperCase())
    .join("");
}

/** Couverture de remplacement : la vraie viendra des API, servie par shelfdrop (CSP : img-src 'self'). */
function Cover({ work }: { readonly work: Work }): ReactElement {
  return (
    <span
      aria-hidden="true"
      className={`flex h-24 w-16 shrink-0 items-center justify-center rounded-md bg-accent-soft text-lg font-semibold text-accent-text`}
    >
      {initials(work.title)}
    </span>
  );
}

export function WorkList({ query, works, selectedId, loading, onChoose, onMerge, onSplit }: Props): ReactElement {
  return (
    <section aria-labelledby="works-title" className="space-y-3">
      <div>
        <h2 id="works-title" className="font-semibold text-ink">
          {texts.works.caption(query)}
        </h2>
      </div>
      {works.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 px-5 py-8 text-center text-sm text-slate-500">
          {texts.works.none(query)}
        </p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {works.map((work) => {
            const active = work.id === selectedId;
            return (
              <li
                key={work.id}
                className={`flex flex-col overflow-hidden rounded-xl border bg-surface transition ${
                  active ? "border-accent ring-2 ring-accent-ring" : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    onChoose(work);
                  }}
                  aria-pressed={active}
                  aria-label={texts.works.choose(work.title)}
                  className="flex w-full flex-1 gap-4 p-4 text-left"
                >
                  <Cover work={work} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className="min-w-0 font-semibold wrap-anywhere text-ink">{work.title}</span>
                      {active ? (
                        loading ? (
                          <Spinner className="size-5 shrink-0 text-accent-text" />
                        ) : (
                          <CheckIcon className="size-5 shrink-0 text-accent-text" />
                        )
                      ) : null}
                    </span>
                    <span className="mt-0.5 block text-sm text-slate-600">
                      {work.author} · {work.year}
                      {work.volumeCount === null ? "" : ` · ${texts.works.volumeCount(work.volumeCount)}`}
                    </span>
                    <span className="mt-2 flex flex-wrap gap-1">
                      {work.titles.slice(1, 4).map((alt) => (
                        <span
                          key={alt.title}
                          className="max-w-full rounded bg-slate-100 px-1.5 py-0.5 text-xs wrap-anywhere text-slate-600"
                        >
                          {alt.title}
                        </span>
                      ))}
                    </span>
                  </span>
                </button>
                <div className="flex items-center justify-between gap-2 border-t border-slate-100 px-4 py-2 text-xs">
                  {work.mergedFrom === undefined ? (
                    <>
                      <span className="text-slate-500">{work.source}</span>
                      <MergeButton work={work} onMerge={onMerge} />
                    </>
                  ) : (
                    <>
                      <span
                        className="flex min-w-0 items-center gap-1 text-accent-text"
                        title={texts.works.mergedTitles(work.mergedFrom.map((part) => part.title))}
                      >
                        <MergeIcon className="size-3.5 shrink-0" />
                        <span className="truncate">{texts.works.mergedFrom(work.mergedFrom.length)}</span>
                      </span>
                      <span className="flex shrink-0 items-center">
                        <MergeButton work={work} onMerge={onMerge} />
                        <button
                          type="button"
                          onClick={() => {
                            onSplit(work);
                          }}
                          aria-label={texts.works.splitLabel(work.title)}
                          className="rounded px-2 py-1 font-medium text-slate-600 hover:bg-slate-100 hover:text-ink"
                        >
                          {texts.works.split}
                        </button>
                      </span>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function MergeButton({ work, onMerge }: { readonly work: Work; readonly onMerge: (work: Work) => void }): ReactElement {
  return (
    <button
      type="button"
      onClick={() => {
        onMerge(work);
      }}
      aria-label={texts.works.mergeLabel(work.title)}
      className="flex items-center gap-1 rounded px-2 py-1 font-medium text-slate-600 hover:bg-slate-100 hover:text-ink"
    >
      <MergeIcon className="size-3.5" />
      {texts.works.merge}
    </button>
  );
}
