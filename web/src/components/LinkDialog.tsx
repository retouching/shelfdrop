import { useEffect, useRef, useState, type ReactElement } from "react";

import { placeFile, type PlaceBody } from "../api/place";
import { texts } from "../texts";
import type { Kind, ShelfFile } from "../types";
import { Spinner } from "./Skeletons";
import { field, guessQuery, WorkPicker, type Pick } from "./WorkPicker";
import { dialogBody, dialogFrame } from "./dialog";

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

/** « Série - T23 - Ch. 206 » quand le tome est connu, « Série - Ch. 230 » sinon. */
export function chapterFileName(series: string, volume: string | null, chapter: string, chapterTo = ""): string {
  const pad = (value: string): string => {
    const number = value.replace(",", ".").replace(/^0+(?=\d)/u, "");
    return number === "" ? "?" : number;
  };
  const range = chapterTo === "" || chapterTo === chapter ? pad(chapter) : `${pad(chapter)}-${pad(chapterTo)}`;
  return volume === null ? `${series} - Ch. ${range}` : `${series} - T${volume} - Ch. ${range}`;
}

type Props = {
  readonly file: ShelfFile;
  readonly onClose: () => void;
  readonly onPlaced: (file: ShelfFile) => void;
};

/** « 12,5 » → 12.5 ; vide → null. */
function chapterNumber(value: string): number | null {
  const number = Number(value.replace(",", "."));
  return value.trim() === "" || Number.isNaN(number) ? null : number;
}

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
  const [refused, setRefused] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const number = volume.trim() === "" ? null : volume.trim().padStart(2, "0");
  const library = texts.libraries[kind];
  const bookFolder = `${number ?? "01"} - ${volumeTitle.trim() === "" ? (pick?.shelfName ?? "") : volumeTitle.trim()}`;
  const destination =
    pick === null
      ? null
      : kind === "manga"
        ? unit === "volume"
          ? [library, pick.shelfName, `${pick.shelfName} - T${number ?? "01"}`]
          : [library, pick.shelfName, chapterFileName(pick.shelfName, number, chapter, chapterTo)]
        : [library, pick.work.author, pick.shelfName, bookFolder];
  const first = chapterNumber(chapter);
  const chapterMissing = kind === "manga" && unit === "chapter" && first === null;

  function body(chosen: Pick): PlaceBody {
    const common = { work_id: chosen.work.id, series: chosen.shelfName, author: chosen.work.author };
    const volumeNumber = number === null ? null : Number(number);
    if (kind === "manga" && unit === "chapter") {
      return { type: "chapter", ...common, first: first ?? 0, last: chapterNumber(chapterTo), volume: volumeNumber };
    }
    return { type: "volume", kind, ...common, volume: volumeNumber, title: volumeTitle.trim() };
  }

  async function place(): Promise<void> {
    if (pick === null || chapterMissing) {
      return;
    }
    setPending(true);
    setRefused(false);
    try {
      onPlaced(await placeFile(file.id, body(pick)));
    } catch {
      setRefused(true);
      setPending(false);
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="link-title" className={dialogFrame.form48}>
      <div className={dialogBody.regular}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="link-title" className="text-lg font-semibold">
            {texts.place.dialogTitle}
          </h2>
          <p className="mt-0.5 truncate text-sm text-slate-500" title={file.path}>
            {texts.place.currentPath} : {file.path}
          </p>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6">
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
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {refused ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.place.errors.refused}
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
            disabled={destination === null || chapterMissing || pending}
            onClick={() => {
              void place();
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.place.moving : texts.place.move}
          </button>
        </div>
      </div>
    </dialog>
  );
}
