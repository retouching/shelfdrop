import { useState, type ReactElement } from "react";

import { wait } from "../mock/latency";
import { setWaiting, useWaiting, type WaitingSearch } from "../mock/waiting";
import { texts } from "../texts";
import { Spinner } from "./Skeletons";

const intervals: readonly number[] = [1, 3, 6, 12, 24];

type Props = {
  readonly onOpen: (search: WaitingSearch) => void;
  readonly onAdd: () => void;
};

export function WaitingPage({ onOpen, onAdd }: Props): ReactElement {
  const searches = useWaiting();
  const [every, setEvery] = useState(6);

  function replace(id: string, change: Partial<WaitingSearch>): void {
    setWaiting(searches.map((search) => (search.id === id ? { ...search, ...change } : search)));
  }

  async function searchNow(search: WaitingSearch): Promise<void> {
    replace(search.id, { state: { kind: "searching" } });
    await wait(1400);
    const clock = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    setWaiting(
      searches.map((entry) =>
        entry.id === search.id
          ? { ...entry, state: { kind: "waiting" }, lastSearch: clock, attempts: entry.attempts + 1 }
          : entry,
      ),
    );
  }

  return (
    <section aria-labelledby="waiting-title" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4">
        <h2 id="waiting-title" className="mr-auto font-semibold text-ink">
          {texts.waiting.title}
        </h2>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          {texts.waiting.every}
          <select
            value={every}
            onChange={(event) => {
              setEvery(Number(event.target.value));
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
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-strong"
        >
          {texts.waiting.addNew}
        </button>
      </div>
      {searches.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-500">{texts.waiting.empty}</p>
      ) : (
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col />
            <col className="w-28" />
            <col className="w-24" />
            <col className="w-44" />
            <col className="w-52" />
            <col className="w-64" />
          </colgroup>
          <thead className="bg-band text-left text-ink">
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
          <tbody className="divide-y divide-slate-100">
            {searches.map((search) => (
              <tr key={search.id}>
                <td className="px-5 py-3">
                  <span className="block truncate font-medium text-ink" title={search.title}>
                    {search.title}
                  </span>
                  <span className="block truncate text-xs text-slate-500">
                    <span className="font-medium text-slate-700">{search.detail}</span> ·{" "}
                    {texts.waiting.names(search.names)}
                  </span>
                </td>
                <td className="px-3 py-3 text-slate-600">{texts.kinds[search.kind]}</td>
                <td className="px-3 py-3 text-slate-500 tabular-nums">{search.addedAt}</td>
                <td className="px-3 py-3 text-xs text-slate-500 tabular-nums">
                  {texts.waiting.last(search.lastSearch, search.attempts)}
                  <span className="block">{texts.waiting.next(search.nextSearch)}</span>
                </td>
                <td className="px-3 py-3">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${
                      search.state.kind === "found"
                        ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                        : search.state.kind === "searching"
                          ? "bg-violet-50 text-violet-700 ring-violet-200"
                          : "bg-slate-100 text-slate-600 ring-slate-200"
                    }`}
                  >
                    {search.state.kind === "searching" ? <Spinner className="size-3" /> : null}
                    {search.state.kind === "found"
                      ? texts.waiting.found(search.state.releases)
                      : search.state.kind === "searching"
                        ? texts.waiting.searching
                        : texts.waiting.nothing}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className="flex justify-end gap-2">
                    {search.state.kind === "found" ? (
                      <button
                        type="button"
                        onClick={() => {
                          onOpen(search);
                        }}
                        className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-strong"
                      >
                        {texts.waiting.open}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={search.state.kind === "searching"}
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
                        setWaiting(searches.filter((entry) => entry.id !== search.id));
                      }}
                      aria-label={texts.waiting.removeFor(search.title)}
                      className="rounded-lg px-3 py-1.5 text-xs text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                    >
                      {texts.waiting.remove}
                    </button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
