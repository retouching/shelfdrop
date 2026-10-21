import { useEffect, useRef, useState, type ReactElement } from "react";

import { wait } from "../../mock/latency";
import { mockSeries, type LibraryName, type Series } from "../../mock/library";
import { texts } from "../../texts";
import { SearchIcon } from "../icons";
import { RefreshBar } from "../RefreshBar";
import { Spinner } from "../Skeletons";
import { field } from "../WorkPicker";
import { Cover } from "./Cover";
import { scanModes, type ScanMode } from "./scan";
import { SeriesEditor } from "./SeriesEditor";

type Filter = "all" | "noImage" | "noSummary";
const filters: readonly Filter[] = ["all", "noImage", "noSummary"];
const libraries: readonly (LibraryName | "all")[] = ["all", "comics", "books", "audiobooks"];

function lacksSummary(series: Series): boolean {
  return series.volumesWithoutSummary > 0 || series.summary === "";
}

function matches(series: Series, filter: Filter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "noImage":
      return !series.hasImage;
    case "noSummary":
      return lacksSummary(series);
  }
}

export function LibraryPage(): ReactElement {
  const [all, setAll] = useState<readonly Series[]>(mockSeries);
  const [filter, setFilter] = useState<Filter>("all");
  const [library, setLibrary] = useState<LibraryName | "all">("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Series | null>(null);
  const [filling, setFilling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState(() => new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [scan, setScan] = useState<number | null>(null);
  const [scanMode, setScanMode] = useState<ScanMode>("new");

  async function refresh(): Promise<void> {
    setRefreshing(true);
    await wait(700);
    setUpdatedAt(new Date());
    setRefreshing(false);
  }

  async function rescan(): Promise<void> {
    setNotice(null);
    for (let percent = 0; percent <= 100; percent += 10) {
      setScan(percent);
      await wait(350);
    }
    setScan(null);
    setUpdatedAt(new Date());
    setNotice(texts.scan.done);
  }

  const inLibrary = all.filter(
    (series) =>
      (library === "all" || series.library === library) &&
      series.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const shown = inLibrary.filter((series) => matches(series, filter));
  const fillable = inLibrary.filter((series) => lacksSummary(series) && series.proposedSummary !== null);

  function replace(next: Series): void {
    setAll((current) => current.map((series) => (series.id === next.id ? next : series)));
  }

  return (
    <div className="space-y-6">
      <RefreshBar
        updatedAt={updatedAt}
        refreshing={refreshing}
        onRefresh={() => {
          void refresh();
        }}
      >
        <span className="flex items-center gap-2 border-l border-slate-200 pl-3">
          <label className="text-sm">
            <span className="sr-only">{texts.scan.mode}</span>
            <select
              value={scanMode}
              disabled={scan !== null}
              onChange={(event) => {
                setScanMode(event.target.value as ScanMode);
              }}
              className="rounded-lg border border-slate-200 bg-surface px-2 py-1.5 text-sm"
            >
              {scanModes.map((mode) => (
                <option key={mode} value={mode}>
                  {texts.scan.modes[mode]}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={scan !== null}
            onClick={() => {
              void rescan();
            }}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-surface px-3 py-1.5 text-sm hover:bg-slate-50 disabled:cursor-wait"
          >
            {scan === null ? null : <Spinner className="size-3.5" />}
            {scan === null
              ? library === "all"
                ? texts.scan.scan
                : texts.scan.scanLibrary(texts.library.libraries[library])
              : texts.scan.scanning(scan)}
          </button>
        </span>
      </RefreshBar>
      {scan === null ? null : (
        <progress
          max={100}
          value={scan}
          aria-label={texts.scan.scanning(scan)}
          className="block h-1 w-full overflow-hidden rounded [&::-moz-progress-bar]:bg-violet-500 [&::-webkit-progress-bar]:bg-slate-100 [&::-webkit-progress-value]:bg-violet-500"
        />
      )}
      <div className="flex flex-wrap items-end gap-4">
        <div role="radiogroup" aria-label={texts.library.filter} className="flex rounded-lg bg-slate-100 p-1">
          {filters.map((option) => {
            const count = inLibrary.filter((series) => matches(series, option)).length;
            return (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={option === filter}
                onClick={() => {
                  setFilter(option);
                }}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm ${
                  option === filter ? "bg-surface font-medium text-ink shadow-sm" : "text-slate-500 hover:text-ink"
                }`}
              >
                {texts.library.filters[option]}
                <span className="text-xs text-slate-500 tabular-nums">{count}</span>
              </button>
            );
          })}
        </div>
        <label className="space-y-1">
          <span className="block text-xs text-slate-500">{texts.library.libraryLabel}</span>
          <select
            value={library}
            onChange={(event) => {
              setLibrary(event.target.value as LibraryName | "all");
            }}
            className={`${field} w-44`}
          >
            {libraries.map((option) => (
              <option key={option} value={option}>
                {texts.library.libraries[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="relative flex-1">
          <span className="sr-only">{texts.library.search}</span>
          <SearchIcon className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            placeholder={texts.library.search}
            className={`${field} pl-9`}
          />
        </label>
        <button
          type="button"
          disabled={fillable.length === 0}
          onClick={() => {
            setFilling(true);
          }}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          {texts.library.fillSummaries(fillable.length)}
        </button>
      </div>

      {notice === null ? null : (
        <p role="status" className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </p>
      )}

      <p className="text-sm text-slate-500">{texts.library.count(shown.length)}</p>
      {shown.length === 0 ? (
        <p className="py-10 text-center text-slate-500">{texts.library.empty}</p>
      ) : (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-5">
          {shown.map((series) => (
            <li key={series.id}>
              <button
                type="button"
                onClick={() => {
                  setEditing(series);
                }}
                aria-label={texts.library.edit(series.name)}
                className="group w-full space-y-2 text-left"
              >
                <Cover
                  hue={series.hasImage ? series.hue : null}
                  label={series.name}
                  className="aspect-[2/3] w-full transition group-hover:ring-2 group-hover:ring-accent"
                />
                <span className="block truncate text-sm font-medium text-ink">{series.name}</span>
                <span className="block text-xs text-slate-500">
                  {texts.library.libraries[series.library]} · {texts.library.volumes(series.volumes)}
                </span>
                <span className="flex flex-wrap gap-1">
                  {series.hasImage ? null : <Badge tone="rose">{texts.library.noImage}</Badge>}
                  {lacksSummary(series) ? (
                    <Badge tone="amber">
                      {texts.library.noSummary(
                        Math.max(series.volumesWithoutSummary, 1),
                        series.volumesWithoutSummary === 0 ? 1 : series.volumes,
                      )}
                    </Badge>
                  ) : null}
                  {series.hasImage && !lacksSummary(series) ? (
                    <Badge tone="emerald">{texts.library.complete}</Badge>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {editing === null ? null : (
        <SeriesEditor
          series={editing}
          onClose={() => {
            setEditing(null);
          }}
          onApplied={(next) => {
            replace(next);
            setNotice(texts.library.applied(next.name));
          }}
          onRescanned={(name) => {
            setNotice(texts.scan.seriesDone(name));
          }}
        />
      )}
      {filling ? (
        <FillDialog
          series={fillable}
          onClose={() => {
            setFilling(false);
          }}
          onApplied={(ids) => {
            setAll((current) =>
              current.map((series) =>
                ids.has(series.id)
                  ? {
                      ...series,
                      summary: series.summary === "" ? (series.proposedSummary?.text ?? "") : series.summary,
                      volumesWithoutSummary: 0,
                      proposedSummary: null,
                    }
                  : series,
              ),
            );
            setNotice(texts.library.appliedMany(ids.size));
          }}
        />
      ) : null}
    </div>
  );
}

function Badge({
  tone,
  children,
}: {
  readonly tone: "rose" | "amber" | "emerald";
  readonly children: string;
}): ReactElement {
  const tones = {
    rose: "bg-rose-50 text-rose-700 ring-rose-200",
    amber: "bg-amber-50 text-amber-800 ring-amber-200",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  };
  return <span className={`rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset ${tones[tone]}`}>{children}</span>;
}

function FillDialog({
  series,
  onClose,
  onApplied,
}: {
  readonly series: readonly Series[];
  readonly onClose: () => void;
  readonly onApplied: (ids: ReadonlySet<string>) => void;
}): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set(series.map((entry) => entry.id)));
  const [pending, setPending] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function apply(): Promise<void> {
    setPending(true);
    await wait(1200);
    onApplied(picked);
    ref.current?.close();
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="fill-title"
      className="m-auto max-h-[90vh] w-full max-w-3xl rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="flex max-h-[90vh] flex-col">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 id="fill-title" className="text-lg font-semibold">
            {texts.library.fillTitle}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">{texts.library.fillLead}</p>
        </div>
        <ul className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto px-6">
          {series.map((entry) => (
            <li key={entry.id}>
              <label className="flex gap-3 py-4">
                <input
                  type="checkbox"
                  checked={picked.has(entry.id)}
                  onChange={(event) => {
                    const next = new Set(picked);
                    if (event.target.checked) {
                      next.add(entry.id);
                    } else {
                      next.delete(entry.id);
                    }
                    setPicked(next);
                  }}
                  className="mt-1 size-4 accent-accent"
                />
                <Cover hue={entry.hasImage ? entry.hue : null} label={entry.name} className="h-16 w-11" bare />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-medium">{entry.name}</span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {entry.proposedSummary?.source} · {texts.library.volumes(entry.volumesWithoutSummary)}
                    </span>
                  </span>
                  <span className="mt-1 block text-sm text-slate-600">
                    {entry.proposedSummary?.text ?? texts.library.fillNone}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
          <button
            type="button"
            onClick={() => {
              ref.current?.close();
            }}
            className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            {texts.dialog.cancel}
          </button>
          <button
            type="button"
            disabled={picked.size === 0 || pending}
            onClick={() => {
              void apply();
            }}
            className="flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.library.applying : texts.library.fillApply(picked.size)}
          </button>
        </div>
      </div>
    </dialog>
  );
}
