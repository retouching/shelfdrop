import { useEffect, useRef, useState, type ReactElement } from "react";

import { wait } from "../mock/latency";
import { texts } from "../texts";
import type { Kind, ShelfFile } from "../types";
import { Spinner } from "./Skeletons";
import { field, guessQuery, WorkPicker, type Pick } from "./WorkPicker";

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

/** « Série - T23 - Ch. 206 » quand le tome est connu, « Série - Ch. 230 » sinon. */
export function chapterFileName(series: string, volume: string | null, chapter: string, chapterTo = ""): string {
  const pad = (value: string): string => {
    const number = value.replace(",", ".");
    return number === "" ? "?" : number.replace(/^(\d+)/u, (whole) => whole.padStart(3, "0"));
  };
  const range = chapterTo === "" || chapterTo === chapter ? pad(chapter) : `${pad(chapter)}-${pad(chapterTo)}`;
  return volume === null ? `${series} - Ch. ${range}` : `${series} - T${volume} - Ch. ${range}`;
}

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
  // Manga : un fichier est un tome, ou un chapitre (avec ou sans tome).
  const [unit, setUnit] = useState<"volume" | "chapter">(() =>
    /\b(ch(ap(itre)?)?\.?\s?\d|c\d{2,})/iu.test(file.name) ? "chapter" : "volume",
  );
  // « Ch. 206 » ou « Ch. 206-210 » : un fichier peut porter une plage de chapitres.
  const [chapterRange] = useState(
    () => /ch(?:ap(?:itre)?)?\.?\s?(\d+(?:[.,]\d)?)(?:\s?(?:-|à)\s?(\d+(?:[.,]\d)?))?/iu.exec(file.name) ?? null,
  );
  const [chapter, setChapter] = useState(chapterRange?.[1] ?? "");
  const [chapterTo, setChapterTo] = useState(chapterRange?.[2] ?? "");
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
        ? unit === "volume"
          ? [library, pick.shelfName, `${pick.shelfName} - T${number ?? "01"}`]
          : [library, pick.shelfName, chapterFileName(pick.shelfName, number, chapter, chapterTo)]
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

          {pick === null || kind !== "manga" ? null : (
            <div role="radiogroup" aria-label={texts.place.unit} className="inline-flex rounded-lg bg-slate-100 p-1">
              {(["volume", "chapter"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={option === unit}
                  onClick={() => {
                    setUnit(option);
                  }}
                  className={
                    option === unit
                      ? "rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-ink shadow-sm"
                      : "rounded-md px-3 py-1.5 text-sm text-slate-500 hover:text-ink"
                  }
                >
                  {texts.place.units[option]}
                </button>
              ))}
            </div>
          )}

          {pick === null || kind !== "manga" || unit !== "chapter" ? null : (
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.place.chapter}</span>
                <input
                  value={chapter}
                  inputMode="decimal"
                  onChange={(event) => {
                    setChapter(event.target.value.replace(/[^\d.,]/gu, ""));
                  }}
                  className={field}
                />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.place.chapterTo}</span>
                <input
                  value={chapterTo}
                  inputMode="decimal"
                  onChange={(event) => {
                    setChapterTo(event.target.value.replace(/[^\d.,]/gu, ""));
                  }}
                  className={field}
                />
                <span className="block text-xs text-slate-500">{texts.place.chapterToHint}</span>
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.place.chapterVolume}</span>
                <input
                  value={volume}
                  inputMode="numeric"
                  onChange={(event) => {
                    setVolume(event.target.value.replace(/\D/gu, ""));
                  }}
                  className={field}
                />
                <span className="block text-xs text-slate-500">{texts.place.chapterVolumeHint}</span>
              </label>
            </div>
          )}

          {pick === null || (kind === "manga" && unit === "chapter") ? null : (
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
              {kind === "manga" && unit === "chapter" ? (
                <p className="mt-1 text-xs text-slate-500">{texts.place.chapterOrder}</p>
              ) : null}
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
