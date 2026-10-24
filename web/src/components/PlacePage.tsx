import { useState, type ReactElement } from "react";

import { askScan } from "../api/place";
import { texts } from "../texts";
import type { FileState, Kind, ShelfFile } from "../types";
import { formatSize } from "../utils/format";
import { SearchIcon } from "./icons";
import { ChaptersDialog } from "./ChaptersDialog";
import { LinkDialog } from "./LinkDialog";

/** La raison d'un fichier mal rangé, en clair ; une raison inconnue reste telle quelle. */
function reasonText(reason: string, kind: Kind | null): string {
  switch (reason) {
    case "root":
      return texts.place.reasons.root(kind === null ? "" : texts.libraries[kind]);
    case "naming":
    case "tracks":
    case "chapters":
    case "relink":
      return texts.place.reasons[reason];
    default:
      return reason;
  }
}

function errorText(error: string): string {
  return error in texts.place.errors
    ? texts.place.errors[error as keyof typeof texts.place.errors]
    : texts.place.errors.refused;
}

function stateText(state: FileState, kind: Kind | null): string {
  switch (state.kind) {
    case "uploading":
      return texts.place.uploading(state.percent);
    case "uploadFailed":
      return texts.place.uploadFailed[state.reason];
    case "unlinked":
      return texts.place.unlinked;
    case "chapters":
      return texts.chapters.state;
    case "misplaced":
      return texts.place.misplaced(reasonText(state.reason, kind));
    case "placing":
      return texts.place.placing;
    case "placed":
      return texts.place.placed(state.destination);
  }
}

function stateTone(state: FileState): string {
  switch (state.kind) {
    case "uploading":
    case "placing":
      return "bg-violet-50 text-violet-700 ring-violet-200";
    case "unlinked":
    case "chapters":
      return "bg-amber-50 text-amber-800 ring-amber-200";
    case "misplaced":
    case "uploadFailed":
      return "bg-rose-50 text-rose-700 ring-rose-200";
    case "placed":
      return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  }
}

function needsAction(file: ShelfFile): boolean {
  return file.state.kind === "unlinked" || file.state.kind === "misplaced" || file.state.kind === "chapters";
}

type Props = {
  readonly files: readonly ShelfFile[];
  readonly onPlaced: (file: ShelfFile) => void;
  /** Le texte cherché : il cherche aussi dans les fichiers déjà rangés de la bibliothèque. */
  readonly onSearch: (text: string) => void;
};

export function PlacePage({ files, onPlaced, onSearch }: Props): ReactElement {
  const [filter, setFilter] = useState<"todo" | "all">("todo");
  const [query, setQuery] = useState("");
  const [scanAsked, setScanAsked] = useState(false);
  const [linking, setLinking] = useState<ShelfFile | null>(null);
  const [chaptering, setChaptering] = useState<ShelfFile | null>(null);

  const needle = query.trim().toLowerCase();
  const shown = files.filter(
    (file) =>
      (filter === "all" || needsAction(file) || file.state.kind === "uploading") &&
      (needle === "" || file.path.toLowerCase().includes(needle)),
  );

  return (
    <div className="space-y-6">
      <section aria-labelledby="files-title" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4">
          <h2 id="files-title" className="mr-auto font-semibold text-ink">
            {texts.place.filesTitle}
          </h2>
          <button
            type="button"
            disabled={scanAsked}
            onClick={() => {
              setScanAsked(true);
              askScan().catch(() => {
                setScanAsked(false);
              });
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {scanAsked ? texts.place.scanAsked : texts.place.scan}
          </button>
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                onSearch(event.target.value.trim());
                if (event.target.value !== "") {
                  setFilter("all");
                }
              }}
              aria-label={texts.place.filter}
              placeholder={texts.place.filterPlaceholder}
              className="w-72 rounded-lg border border-slate-200 py-1.5 pr-3 pl-9 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring"
            />
          </div>
          <div
            role="radiogroup"
            aria-label={texts.place.filesTitle}
            className="inline-flex rounded-lg bg-slate-100 p-1"
          >
            {(["todo", "all"] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={option === filter}
                onClick={() => {
                  setFilter(option);
                }}
                className={
                  option === filter
                    ? "rounded-md bg-surface px-3 py-1 text-sm font-medium text-ink shadow-sm"
                    : "rounded-md px-3 py-1 text-sm text-slate-500 hover:text-ink"
                }
              >
                {texts.place.filters[option]}
              </button>
            ))}
          </div>
        </div>
        {shown.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-slate-500">
            {needle === "" ? texts.place.allPlaced : texts.place.none}
          </p>
        ) : (
          <table className="w-full table-fixed text-sm">
            <colgroup>
              <col />
              <col className="w-32" />
              <col className="w-24" />
              <col className="w-72" />
              <col className="w-28" />
            </colgroup>
            <thead className="bg-band text-left text-ink">
              <tr>
                <th scope="col" className="px-5 py-3 font-semibold">
                  {texts.place.file}
                </th>
                <th scope="col" className="px-3 py-3 font-semibold">
                  {texts.place.origin}
                </th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">
                  {texts.results.size}
                </th>
                <th scope="col" className="px-3 py-3 font-semibold">
                  {texts.place.state}
                </th>
                <th scope="col" className="px-5 py-3">
                  <span className="sr-only">{texts.place.link}</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((file) => (
                <tr key={file.id}>
                  <td className="px-5 py-2.5">
                    <span className="block truncate font-medium text-ink" title={file.name}>
                      {file.name}
                    </span>
                    <span className="block truncate text-xs text-slate-500" title={file.path}>
                      {file.kind === null ? texts.place.unknownKind : texts.kinds[file.kind]} · {file.path}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-slate-600">{texts.place.origins[file.origin]}</td>
                  <td className="px-3 py-3 text-right whitespace-nowrap text-slate-500 tabular-nums">
                    {formatSize(file.sizeBytes)}
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={`inline-block max-w-full truncate rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${stateTone(file.state)}`}
                      title={stateText(file.state, file.kind)}
                    >
                      {stateText(file.state, file.kind)}
                    </span>
                    {file.error === undefined || file.error === null ? null : (
                      <span className="mt-1 block truncate text-xs text-rose-700" title={errorText(file.error)}>
                        {errorText(file.error)}
                      </span>
                    )}
                    {file.state.kind === "uploading" ? (
                      <progress
                        max={100}
                        value={file.state.percent}
                        aria-hidden="true"
                        className="mt-1.5 block h-1 w-full overflow-hidden rounded [&::-moz-progress-bar]:bg-violet-500 [&::-webkit-progress-bar]:bg-slate-100 [&::-webkit-progress-value]:bg-violet-500"
                      />
                    ) : null}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {file.state.kind === "chapters" ? (
                      <button
                        type="button"
                        onClick={() => {
                          setChaptering(file);
                        }}
                        aria-label={texts.chapters.linkFor(file.name)}
                        className="rounded-lg border border-transparent bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-strong"
                      >
                        {texts.chapters.open}
                      </button>
                    ) : file.state.kind === "uploading" || file.state.kind === "placing" ? null : (
                      <button
                        type="button"
                        onClick={() => {
                          setLinking(file);
                        }}
                        aria-label={texts.place.linkFor(file.name)}
                        className={
                          needsAction(file)
                            ? "rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-strong"
                            : "rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                        }
                      >
                        {needsAction(file) ? texts.place.link : texts.place.relink}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {chaptering?.chapters === undefined ? null : (
        <ChaptersDialog
          file={chaptering}
          chapters={chaptering.chapters.numbers}
          existing={chaptering.chapters.existing}
          loose={chaptering.chapters.loose}
          onClose={() => {
            setChaptering(null);
          }}
          onPlaced={(file) => {
            onPlaced(file);
            setChaptering(null);
          }}
        />
      )}
      {linking === null ? null : (
        <LinkDialog
          file={linking}
          onClose={() => {
            setLinking(null);
          }}
          onPlaced={(file) => {
            onPlaced(file);
            setLinking(null);
          }}
        />
      )}
    </div>
  );
}
