import { useState, type ReactElement } from "react";

import { removeWaiting, saveInterval, searchWaitingNow, useWaiting, type WaitingSearch } from "../api/waiting";
import { locale, texts } from "../texts";
import { stacked } from "./stacked";
import { Spinner } from "./Skeletons";

const intervals: readonly number[] = [1, 3, 6, 12, 24];

type Props = {
  readonly onOpen: (search: WaitingSearch) => void;
  readonly onAdd: () => void;
};

function clockOf(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

function dayOf(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString(locale, { day: "2-digit", month: "2-digit" });
}

export function WaitingPage({ onOpen, onAdd }: Props): ReactElement {
  const list = useWaiting(true);
  const searches = list?.searches ?? [];
  const every = list?.everyHours ?? 6;
  const [searching, setSearching] = useState<ReadonlySet<number>>(() => new Set());
  const [error, setError] = useState(false);

  async function searchNow(search: WaitingSearch): Promise<void> {
    setSearching((current) => new Set(current).add(search.id));
    setError(false);
    try {
      await searchWaitingNow(search.id);
    } catch {
      setError(true);
    } finally {
      setSearching((current) => {
        const next = new Set(current);
        next.delete(search.id);
        return next;
      });
    }
  }

  async function remove(search: WaitingSearch): Promise<void> {
    setError(false);
    try {
      await removeWaiting(search.id);
    } catch {
      setError(true);
    }
  }

  return (
    <section aria-labelledby="waiting-title" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-4 md:px-5">
        <h2 id="waiting-title" className="mr-auto font-semibold text-ink">
          {texts.waiting.title}
        </h2>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          {texts.waiting.every}
          <select
            value={every}
            onChange={(event) => {
              saveInterval(Number(event.target.value)).catch(() => {
                setError(true);
              });
            }}
            className="rounded-lg border border-slate-200 bg-surface px-2 py-1 text-sm"
          >
            {intervals.map((hours) => (
              <option key={hours} value={hours}>
                {texts.waiting.hours(hours)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onAdd}
          className="rounded-lg border border-transparent bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-strong"
        >
          {texts.waiting.addNew}
        </button>
      </div>
      {error ? (
        <p role="alert" className="border-b border-slate-200 bg-rose-50 px-5 py-3 text-sm text-rose-800">
          {texts.waiting.failed}
        </p>
      ) : null}
      {list === null ? (
        <p className="flex items-center justify-center gap-2 px-5 py-10 text-sm text-slate-500">
          <Spinner /> {texts.waiting.loading}
        </p>
      ) : searches.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-500">{texts.waiting.empty}</p>
      ) : (
        <table className={`${stacked.table} w-full md:table-fixed`}>
          <colgroup className={stacked.columns}>
            <col />
            <col className="w-28" />
            <col className="w-24" />
            <col className="w-44" />
            <col className="w-52" />
            <col className="w-64" />
          </colgroup>
          <thead className={stacked.head}>
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">
                {texts.waiting.work}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.downloads.kind}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.waiting.since}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.waiting.searches}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.downloads.state}
              </th>
              <th scope="col" className="px-5 py-3">
                <span className="sr-only">{texts.downloads.actions}</span>
              </th>
            </tr>
          </thead>
          <tbody className={`${stacked.body} divide-slate-100`}>
            {searches.map((search) => {
              const state = searching.has(search.id) ? "searching" : search.state.kind;
              return (
                <tr key={search.id} className={stacked.row}>
                  <td className={`${stacked.cell} basis-full md:px-5 md:py-3`}>
                    <span className="block font-medium wrap-anywhere text-ink md:truncate" title={search.title}>
                      {search.title}
                    </span>
                    <span className="block text-xs wrap-anywhere text-slate-500 md:truncate">
                      <span className="font-medium text-slate-700">{search.detail}</span> ·{" "}
                      {texts.waiting.names(search.names.length)}
                    </span>
                  </td>
                  <td className={`${stacked.cell} text-xs text-slate-600 md:px-3 md:py-3 md:text-sm`}>
                    {texts.kinds[search.kind]}
                  </td>
                  <td className={`${stacked.cell} text-xs text-slate-500 tabular-nums md:px-3 md:py-3 md:text-sm`}>
                    <span className={stacked.label}>{texts.waiting.since} </span>
                    {dayOf(search.addedAt)}
                  </td>
                  <td className={`${stacked.cell} basis-full text-xs text-slate-500 tabular-nums md:px-3 md:py-3`}>
                    {search.searchedAt === null
                      ? texts.waiting.never
                      : texts.waiting.last(clockOf(search.searchedAt), search.attempts)}
                    <span className="block">{texts.waiting.next(clockOf(search.nextSearchAt))}</span>
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-3`}>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${
                        search.state.kind === "found"
                          ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                          : state === "searching"
                            ? "bg-violet-50 text-violet-700 ring-violet-200"
                            : "bg-slate-100 text-slate-600 ring-slate-200"
                      }`}
                    >
                      {state === "searching" ? <Spinner className="size-3" /> : null}
                      {search.state.kind === "found"
                        ? texts.waiting.found(search.state.releases)
                        : state === "searching"
                          ? texts.waiting.searching
                          : texts.waiting.nothing}
                    </span>
                  </td>
                  <td className={`${stacked.cell} basis-full md:px-5 md:py-3`}>
                    <span className="flex flex-wrap gap-2 md:justify-end">
                      {search.state.kind === "found" ? (
                        <button
                          type="button"
                          onClick={() => {
                            onOpen(search);
                          }}
                          className="rounded-lg border border-transparent bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-strong"
                        >
                          {texts.waiting.open}
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={state === "searching"}
                          onClick={() => {
                            void searchNow(search);
                          }}
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                        >
                          {texts.waiting.searchNow}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          void remove(search);
                        }}
                        aria-label={texts.waiting.removeFor(search.title)}
                        className="rounded-lg px-3 py-1.5 text-xs text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                      >
                        {texts.waiting.remove}
                      </button>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
