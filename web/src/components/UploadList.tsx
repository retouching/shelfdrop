import type { ReactElement } from "react";

import { texts } from "../texts";
import type { ShelfFile } from "../types";
import { formatSize } from "../utils/format";

type Props = {
  /** Les fichiers envoyés depuis la page pendant cette visite. */
  readonly files: readonly ShelfFile[];
  readonly onPlace: () => void;
  readonly onClear: () => void;
};

/** Ce qu'il reste à dire d'un envoi : sa progression, sa vérification, son arrivée ou son échec. */
function detail(file: ShelfFile): { readonly text: string; readonly tone: string } {
  const state = file.state;
  if (state.kind === "uploadFailed") {
    return { text: texts.place.uploadFailed[state.reason], tone: "text-rose-700" };
  }
  if (state.kind !== "uploading") {
    return { text: "", tone: "text-slate-500" };
  }
  switch (state.phase) {
    case "checking":
      return { text: texts.place.checking, tone: "text-slate-500" };
    case "done":
      return { text: texts.place.uploadedHint, tone: "text-emerald-700" };
    case "sending":
      return {
        text: texts.place.uploadSent(formatSize(state.sent), formatSize(file.sizeBytes), state.percent),
        tone: "text-slate-500",
      };
  }
}

/** La barre d'un envoi : remplie à son pourcentage, pleine une fois vérifié, rouge s'il a échoué. */
function Bar({ file }: { readonly file: ShelfFile }): ReactElement {
  const state = file.state;
  const failed = state.kind === "uploadFailed";
  const percent = state.kind === "uploading" ? (state.phase === "sending" ? state.percent : 100) : 100;
  const checking = state.kind === "uploading" && state.phase === "checking";
  const tone = failed
    ? "bg-rose-400"
    : state.kind === "uploading" && state.phase === "done"
      ? "bg-emerald-500"
      : "bg-accent";
  return (
    <span
      role="progressbar"
      aria-label={file.name}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="block h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
    >
      <span
        className={`block h-full rounded-full transition-[width] duration-300 ${tone} ${checking ? "animate-pulse" : ""}`}
        style={{ width: `${String(percent)}%` }}
      />
    </span>
  );
}

/** Les envois de la page Manuel, chacun avec sa progression ; une fois arrivés, ils sont dans Ranger. */
export function UploadList({ files, onPlace, onClear }: Props): ReactElement {
  const finished = files.some(
    (file) => file.state.kind === "uploadFailed" || (file.state.kind === "uploading" && file.state.phase === "done"),
  );
  const arrived = files.some((file) => file.state.kind === "uploading" && file.state.phase === "done");
  return (
    <section
      aria-labelledby="uploads-title"
      className="space-y-2 rounded-xl border border-slate-200 bg-surface px-4 py-3 md:px-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="uploads-title" className="text-sm font-semibold text-ink">
          {texts.place.uploadsTitle}
        </h2>
        <span className="flex flex-wrap gap-2">
          {arrived ? (
            <button
              type="button"
              onClick={onPlace}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-ink hover:bg-slate-50"
            >
              {texts.place.toPlace}
            </button>
          ) : null}
          {finished ? (
            <button
              type="button"
              onClick={onClear}
              className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              {texts.place.clearUploads}
            </button>
          ) : null}
        </span>
      </div>
      <ul className="divide-y divide-slate-100">
        {files.map((file) => {
          const { text, tone } = detail(file);
          return (
            <li key={file.id} className="space-y-1.5 py-2.5">
              <span className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-sm font-medium text-ink" title={file.name}>
                  {file.name}
                </span>
                <span className="shrink-0 text-xs text-slate-500">{formatSize(file.sizeBytes)}</span>
              </span>
              <Bar file={file} />
              <span role="status" className={`block text-xs ${tone}`}>
                {text}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
