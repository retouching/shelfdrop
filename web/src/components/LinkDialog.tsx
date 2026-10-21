import { useEffect, useRef, useState, type ReactElement } from "react";

import { wait } from "../mock/latency";
import { texts } from "../texts";
import type { Kind, ShelfFile } from "../types";
import { Spinner } from "./Skeletons";
import { field, guessQuery, WorkPicker, type Pick } from "./WorkPicker";

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

type Props = {
  readonly file: ShelfFile;
  readonly onClose: () => void;
  readonly onPlaced: (destination: string) => void;
};

export function LinkDialog({ file, onClose, onPlaced }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<Kind>(file.kind ?? "ebook");
  const [pick, setPick] = useState<Pick | null>(null);
  const [volume, setVolume] = useState(() => /T(\d+)/u.exec(file.name)?.[1] ?? "");
  const [volumeTitle, setVolumeTitle] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const number = volume.trim() === "" ? null : volume.trim().padStart(2, "0");
  const library = texts.libraries[kind];
  const volumePart = [number, volumeTitle.trim() === "" ? null : volumeTitle.trim()]
    .filter((part) => part !== null)
    .join(" - ");
  const destination =
    pick === null
      ? null
      : kind === "manga"
        ? [library, pick.shelfName, `${pick.shelfName} - T${number ?? "01"}`]
        : volumePart === ""
          ? [library, pick.work.author, pick.shelfName]
          : [library, pick.work.author, pick.shelfName, volumePart];

  async function place(): Promise<void> {
    if (destination === null) {
      return;
    }
    setPending(true);
    await wait(900);
    onPlaced(destination.slice(0, -1).join(" › "));
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="link-title"
      className="m-auto max-h-[90vh] w-full max-w-3xl rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="flex max-h-[90vh] flex-col">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 id="link-title" className="text-lg font-semibold">
            {texts.place.dialogTitle}
          </h2>
          <p className="mt-0.5 truncate text-sm text-slate-500" title={file.path}>
            {texts.place.currentPath} : {file.path}
          </p>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          <div role="radiogroup" aria-label={texts.place.kindLabel} className="inline-flex rounded-lg bg-slate-100 p-1">
            {kinds.map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={option === kind}
                onClick={() => {
                  setKind(option);
                  setPick(null);
                }}
                className={
                  option === kind
                    ? "rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-ink shadow-sm"
                    : "rounded-md px-3 py-1.5 text-sm text-slate-500 hover:text-ink"
                }
              >
                {texts.kinds[option]}
              </button>
            ))}
          </div>

          <WorkPicker kind={kind} initialQuery={guessQuery(file.name)} value={pick} onChange={setPick} />

          {pick === null ? null : (
            <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.place.volume}</span>
                <input
                  value={volume}
                  inputMode="numeric"
                  onChange={(event) => {
                    setVolume(event.target.value.replace(/\D/gu, ""));
                  }}
                  className={field}
                />
              </label>
              {kind === "manga" ? null : (
                <label className="block space-y-1.5">
                  <span className="text-sm font-medium">{texts.place.volumeTitle}</span>
                  <input
                    value={volumeTitle}
                    onChange={(event) => {
                      setVolumeTitle(event.target.value);
                    }}
                    className={field}
                  />
                  <span className="block text-xs text-slate-500">{texts.place.volumeTitleHint}</span>
                </label>
              )}
            </div>
          )}

          {destination === null ? null : (
            <div className="rounded-lg bg-band px-4 py-3">
              <p className="text-xs text-slate-500">{texts.place.destination}</p>
              <p className="mt-1 text-sm font-medium break-words">{destination.join(" › ")}</p>
            </div>
          )}
        </div>
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
            disabled={destination === null || pending}
            onClick={() => {
              void place();
            }}
            className="hover:bg-accent-strong-strong flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.place.moving : texts.place.move}
          </button>
        </div>
      </div>
    </dialog>
  );
}
