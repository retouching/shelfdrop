import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";

import {
  fillSummaries,
  itemImage,
  readProposals,
  readScan,
  readSeries,
  startScan,
  type ScanProgress,
  type Series,
} from "../../api/library";
import { texts } from "../../texts";
import type { Kind } from "../../types";
import { SearchIcon } from "../icons";
import { RefreshBar } from "../RefreshBar";
import { Spinner } from "../Skeletons";
import { field } from "../WorkPicker";
import { Cover } from "./Cover";
import { scanModes, type ScanMode } from "./scan";
import { SeriesEditor } from "./SeriesEditor";
import { SyncButton } from "./SyncButton";

type Filter = "all" | "noImage" | "noSummary";
const filters: readonly Filter[] = ["all", "noImage", "noSummary"];
const libraries: readonly (Kind | "all")[] = ["all", "manga", "ebook", "audiobook"];
// Le scan est relu chaque seconde, et tenu pour fini après 3 lectures au repos.
const SCAN_POLL_MS = 1000;
const IDLE_READS = 3;

function percentOf(progress: ScanProgress): number | null {
  const running = Object.values(progress).filter((value): value is number => typeof value === "number");
  return running.length === 0 ? null : Math.round(Math.min(...running));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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
  const [all, setAll] = useState<readonly Series[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [library, setLibrary] = useState<Kind | "all">("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Series | null>(null);
  const [filling, setFilling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState(() => new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [scan, setScan] = useState<number | null>(null);
  const [scanMode, setScanMode] = useState<ScanMode>("new");

  // Le numéro de la dernière lecture : une réponse plus ancienne, arrivée après, est laissée.
  const readsRef = useRef(0);
  const refresh = useCallback(async (): Promise<void> => {
    readsRef.current += 1;
    const read = readsRef.current;
    setRefreshing(true);
    try {
      const found = await readSeries();
      if (read === readsRef.current) {
        setAll(found);
        setError(null);
        setUpdatedAt(new Date());
      }
    } catch {
      if (read === readsRef.current) {
        setError(texts.library.unavailable);
      }
    } finally {
      if (read === readsRef.current) {
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function rescan(): Promise<void> {
    setNotice(null);
    setScan(0);
    try {
      let progress = await startScan(scanMode, library === "all" ? {} : { kind: library });
      let idle = 0;
      while (idle < IDLE_READS) {
        const percent = percentOf(progress);
        idle = percent === null ? idle + 1 : 0;
        setScan(percent ?? 0);
        await sleep(SCAN_POLL_MS);
        progress = await readScan();
      }
      setNotice(texts.scan.done);
      await refresh();
    } catch {
      setError(texts.library.unavailable);
    } finally {
      setScan(null);
    }
  }

  if (all === null) {
    return (
      <div className="space-y-6">
        {error === null ? (
          <p className="flex items-center gap-2 py-10 text-slate-500">
            <Spinner /> {texts.library.loading}
          </p>
        ) : (
          <p role="alert" className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </p>
        )}
      </div>
    );
  }

  const inLibrary = all.filter(
    (series) =>
      (library === "all" || series.kind === library) && series.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const shown = inLibrary.filter((series) => matches(series, filter));
  const fillable = inLibrary.filter(lacksSummary);

  function replace(next: Series): void {
    setAll((current) => (current ?? []).map((series) => (series.id === next.id ? next : series)));
    // La liste est relue ensuite : une lecture partie avant l'enregistrement ne l'écrase pas.
    void refresh();
  }
  // La fiche suit la série relue.
  const edited = editing === null ? null : (all.find((series) => series.id === editing.id) ?? editing);

  return (
    <div className="space-y-6">
      <RefreshBar
        updatedAt={updatedAt}
        refreshing={refreshing}
        onRefresh={() => {
          void refresh();
        }}
      >
        <span className="flex flex-wrap items-center gap-2 md:border-l md:border-slate-200 md:pl-3">
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
          <SyncButton
            seriesId={null}
            question={texts.sync.confirmAll}
            onDone={(message, failed) => {
              if (failed) {
                setError(message);
              } else {
                setNotice(message);
                void refresh();
              }
            }}
          />
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
        <div
          role="radiogroup"
          aria-label={texts.library.filter}
          className="flex w-full flex-wrap rounded-lg bg-slate-100 p-1 md:w-auto"
        >
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
                className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm md:flex-none ${
                  option === filter ? "bg-surface font-medium text-ink shadow-sm" : "text-slate-500 hover:text-ink"
                }`}
              >
                {texts.library.filters[option]}
                <span className="text-xs text-slate-500 tabular-nums">{count}</span>
              </button>
            );
          })}
        </div>
        <label className="w-full space-y-1 sm:w-auto">
          <span className="block text-xs text-slate-500">{texts.library.libraryLabel}</span>
          <select
            value={library}
            onChange={(event) => {
              setLibrary(event.target.value as Kind | "all");
            }}
            className={`${field} sm:w-44`}
          >
            {libraries.map((option) => (
              <option key={option} value={option}>
                {texts.library.libraries[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="relative w-full sm:w-auto sm:flex-1">
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
          className="w-full rounded-lg border border-transparent bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {texts.library.fillSummaries(fillable.length)}
        </button>
      </div>

      {error === null ? null : (
        <p role="alert" className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      {notice === null ? null : (
        <p role="status" className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </p>
      )}

      <p className="text-sm text-slate-500">{texts.library.count(shown.length)}</p>
      {shown.length === 0 ? (
        <p className="py-10 text-center text-slate-500">{texts.library.empty}</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] sm:gap-5">
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
                  src={series.hasImage ? itemImage(series.id, series.imageTag) : null}
                  label={series.name}
                  className="aspect-[2/3] w-full transition group-hover:ring-2 group-hover:ring-accent"
                />
                <span className="block truncate text-sm font-medium text-ink">{series.name}</span>
                <span className="block text-xs text-slate-500">
                  {texts.library.libraries[series.kind]} · {texts.library.volumes(series.volumes)}
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

      {edited === null ? null : (
        <SeriesEditor
          series={edited}
          onClose={() => {
            setEditing(null);
          }}
          onApplied={(next) => {
            replace(next);
            setNotice(texts.library.applied(next.name));
          }}
          onRescanned={(name) => {
            setNotice(texts.scan.seriesDone(name));
            void refresh();
          }}
          onChanged={() => {
            void refresh();
          }}
        />
      )}
      {filling ? (
        <FillDialog
          series={fillable}
          onClose={() => {
            setFilling(false);
          }}
          onApplied={(count) => {
            setNotice(texts.library.appliedMany(count));
            void refresh();
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

type Proposal = { readonly source: string; readonly text: string } | null;

function FillDialog({
  series: given,
  onClose,
  onApplied,
}: {
  readonly series: readonly Series[];
  readonly onClose: () => void;
  readonly onApplied: (count: number) => void;
}): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  // Les séries à l'ouverture : la page peut se relire pendant les recherches.
  const [series] = useState(given);
  const [proposals, setProposals] = useState<ReadonlyMap<string, Proposal>>(() => new Map());
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set());
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const searching = proposals.size < series.length;

  useEffect(() => {
    ref.current?.showModal();
    const run = { stopped: false };
    // Une série après l'autre : chaque recherche interroge toutes les sources.
    void (async () => {
      for (const entry of series) {
        let found: Proposal = null;
        try {
          const read = await readProposals(entry.id);
          found = read.summaries[0] ?? null;
        } catch {
          found = null;
        }
        if (run.stopped) {
          return;
        }
        setProposals((current) => new Map(current).set(entry.id, found));
        if (found !== null) {
          setPicked((current) => new Set(current).add(entry.id));
        }
      }
    })();
    return () => {
      run.stopped = true;
    };
  }, [series]);

  async function apply(): Promise<void> {
    setPending(true);
    setFailed(false);
    const summaries: Record<string, string> = {};
    for (const id of picked) {
      const proposal = proposals.get(id);
      if (proposal !== undefined && proposal !== null) {
        summaries[id] = proposal.text;
      }
    }
    try {
      onApplied(await fillSummaries(summaries));
      ref.current?.close();
    } catch {
      setFailed(true);
      setPending(false);
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="fill-title"
      className="m-auto max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="flex max-h-[calc(90vh-2px)] flex-col">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 id="fill-title" className="text-lg font-semibold">
            {texts.library.fillTitle}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">{texts.library.fillLead}</p>
          {searching ? (
            <p role="status" className="mt-2 flex items-center gap-2 text-sm text-slate-500">
              <Spinner className="size-3.5" /> {texts.library.fillSearching(proposals.size, series.length)}
            </p>
          ) : null}
        </div>
        <ul className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto px-6">
          {series.map((entry) => {
            const proposal = proposals.get(entry.id);
            return (
              <li key={entry.id}>
                <label className="flex gap-3 py-4">
                  <input
                    type="checkbox"
                    checked={picked.has(entry.id)}
                    disabled={proposal === undefined || proposal === null}
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
                  <Cover
                    src={entry.hasImage ? itemImage(entry.id, entry.imageTag, 120) : null}
                    label={entry.name}
                    className="h-16 w-11"
                    bare
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="font-medium">{entry.name}</span>
                      <span className="shrink-0 text-xs text-slate-500">
                        {proposal?.source ?? ""} · {texts.library.volumes(entry.volumesWithoutSummary)}
                      </span>
                    </span>
                    <span className="mt-1 line-clamp-4 block text-sm text-slate-600">
                      {proposal === undefined ? (
                        <Spinner className="size-3.5" />
                      ) : (
                        (proposal?.text ?? texts.library.fillNone)
                      )}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-6 py-4">
          {failed ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.library.failed}
            </p>
          ) : null}
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
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.library.applying : texts.library.fillApply(picked.size)}
          </button>
        </div>
      </div>
    </dialog>
  );
}
