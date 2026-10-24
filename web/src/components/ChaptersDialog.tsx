import { useEffect, useRef, useState, type ReactElement } from "react";

import { placeFile } from "../api/place";
import { locale, texts } from "../texts";
import type { ShelfFile } from "../types";
import { Spinner } from "./Skeletons";
import { field, guessQuery, WorkPicker, type Pick } from "./WorkPicker";
import { dialogBody, dialogFrame } from "./dialog";

type Props = {
  readonly file: ShelfFile;
  readonly chapters: readonly number[];
  /** Tomes déjà dans la bibliothèque pour cette série. */
  readonly existing: readonly number[];
  /** Chapitres déjà rangés seuls dans le dossier de cette série : le serveur les compte pour un tome complet. */
  readonly loose: readonly number[];
  readonly onClose: () => void;
  readonly onPlaced: (file: ShelfFile) => void;
};

type Link = { readonly volume: number; readonly from: number; readonly to: number };

/** Teintes des tomes, en boucle : un tome = une couleur sur la grille des chapitres. */
const tones = [
  "bg-violet-200 text-violet-900",
  "bg-sky-200 text-sky-900",
  "bg-emerald-200 text-emerald-900",
  "bg-amber-200 text-amber-900",
  "bg-pink-200 text-pink-900",
  "bg-teal-200 text-teal-900",
];

/** « 212 à 214 », « 98, 212 à 214 » : les chapitres manquants, en plages. */
function missingLabel(missing: readonly number[]): string {
  const parts: string[] = [];
  let start = missing[0];
  let previous = start;
  for (const chapter of [...missing.slice(1), Number.NaN]) {
    if (start === undefined || previous === undefined) {
      break;
    }
    if (chapter !== previous + 1) {
      parts.push(start === previous ? String(start) : texts.chapters.missingRange(String(start), String(previous)));
      start = chapter;
    }
    previous = chapter;
  }
  return parts.join(", ");
}

function chapterLabel(chapter: number): string {
  return Number.isInteger(chapter) ? String(chapter) : chapter.toLocaleString(locale);
}

export function ChaptersDialog({ file, chapters, existing, loose, onClose, onPlaced }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [pick, setPick] = useState<Pick | null>(null);
  const [links, setLinks] = useState<readonly Link[]>([]);
  const [from, setFrom] = useState<number | null>(null);
  const [to, setTo] = useState<number | null>(null);
  const [volume, setVolume] = useState(() => String((existing.at(-1) ?? 0) + 1));
  const [rest, setRest] = useState<"place" | "keep">("place");
  const [replace, setReplace] = useState<ReadonlySet<number>>(() => new Set());
  const [pending, setPending] = useState(false);
  const [refused, setRefused] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const linkOf = (chapter: number): Link | undefined =>
    links.find((link) => chapter >= link.from && chapter <= link.to);
  const toneOf = (link: Link): string => tones[links.indexOf(link) % tones.length] ?? "";
  const low = from === null ? null : to === null ? from : Math.min(from, to);
  const high = from === null ? null : to === null ? from : Math.max(from, to);
  const inRange = (chapter: number): boolean => low !== null && high !== null && chapter >= low && chapter <= high;
  const free = chapters.filter((chapter) => linkOf(chapter) === undefined);
  const volumeNumber = Number(volume);
  const canLink =
    low !== null &&
    high !== null &&
    Number.isInteger(volumeNumber) &&
    volumeNumber > 0 &&
    !links.some((link) => link.volume === volumeNumber || (link.from <= high && low <= link.to));
  const written = links.filter((link) => !existing.includes(link.volume) || replace.has(link.volume));
  const complete = written.filter((link) => missingOf(link).length === 0);
  const looseCount =
    written.filter((link) => missingOf(link).length > 0).reduce((sum, link) => sum + presentOf(link).length, 0) +
    (rest === "place" ? free.length : 0);

  function presentOf(link: Link): readonly number[] {
    return chapters.filter((chapter) => chapter >= link.from && chapter <= link.to);
  }

  /** Les chapitres entiers de la plage absents de la release et du dossier de la série (les « .5 » ne sont
   * jamais attendus) : le serveur décide pareil. Ceux du dossier ne comptent que pour la série du fichier. */
  function missingOf(link: Link): readonly number[] {
    const shelved = pick === null || pick.shelfName === file.series ? loose : [];
    const missing: number[] = [];
    for (let chapter = Math.ceil(link.from); chapter <= link.to; chapter += 1) {
      if (!chapters.includes(chapter) && !shelved.includes(chapter)) {
        missing.push(chapter);
      }
    }
    return missing;
  }

  function choose(chapter: number, extend: boolean): void {
    if (linkOf(chapter) !== undefined) {
      return;
    }
    if (from === null || !extend) {
      setFrom(chapter);
      setTo(null);
    } else {
      setTo(chapter);
    }
  }

  function link(): void {
    if (!canLink) {
      return;
    }
    const next = [...links, { volume: volumeNumber, from: low, to: high }].sort((a, b) => a.volume - b.volume);
    setLinks(next);
    setFrom(null);
    setTo(null);
    setVolume(String(Math.max(volumeNumber, ...next.map((entry) => entry.volume)) + 1));
  }

  async function place(): Promise<void> {
    if (pick === null) {
      return;
    }
    setPending(true);
    setRefused(false);
    try {
      const placed = await placeFile(file.id, {
        type: "chapters",
        work_id: pick.work.id,
        series: pick.shelfName,
        author: pick.work.author,
        summary: "",
        volumes: links.map((entry) => ({
          volume: entry.volume,
          first: entry.from,
          last: entry.to,
          replace: replace.has(entry.volume),
        })),
        rest,
      });
      onPlaced(placed);
      ref.current?.close();
    } catch {
      setRefused(true);
      setPending(false);
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="chapters-title" className={dialogFrame.form72}>
      <div className={dialogBody.taller}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="chapters-title" className="text-lg font-semibold">
            {texts.chapters.title}
          </h2>
          <p className="mt-0.5 truncate text-sm text-slate-500" title={file.path}>
            {file.name} · {texts.chapters.count(chapters.length)}
          </p>
        </div>

        <div className="grid min-h-0 flex-1 gap-6 overflow-y-auto px-4 py-5 md:px-6 lg:grid-cols-[1fr_22rem]">
          <div className="space-y-5">
            <WorkPicker
              kind="manga"
              initialQuery={file.series === undefined || file.series === "" ? guessQuery(file.name) : file.series}
              value={pick}
              onChange={setPick}
            />

            <section aria-labelledby="chapters-grid" className="space-y-3">
              <div className="flex flex-wrap items-end gap-3">
                <h3 id="chapters-grid" className="w-full text-sm font-semibold">
                  {texts.chapters.grid}
                </h3>
                <label className="space-y-1">
                  <span className="block text-xs text-slate-500">{texts.chapters.from}</span>
                  <input
                    value={low ?? ""}
                    inputMode="decimal"
                    onChange={(event) => {
                      setFrom(event.target.value === "" ? null : Number(event.target.value));
                    }}
                    className={`${field} w-24 py-1 text-sm`}
                  />
                </label>
                <label className="space-y-1">
                  <span className="block text-xs text-slate-500">{texts.chapters.to}</span>
                  <input
                    value={to ?? ""}
                    inputMode="decimal"
                    disabled={from === null}
                    onChange={(event) => {
                      setTo(event.target.value === "" ? null : Number(event.target.value));
                    }}
                    className={`${field} w-24 py-1 text-sm`}
                  />
                </label>
                <label className="space-y-1">
                  <span className="block text-xs text-slate-500">{texts.chapters.volume}</span>
                  <input
                    value={volume}
                    inputMode="numeric"
                    onChange={(event) => {
                      setVolume(event.target.value);
                    }}
                    className={`${field} w-20 py-1 text-sm`}
                  />
                </label>
                <button
                  type="button"
                  disabled={!canLink}
                  onClick={link}
                  className="rounded-lg border border-transparent bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {texts.chapters.link(volume)}
                </button>
              </div>
              <p className="text-xs text-slate-500">{texts.chapters.gridHint}</p>
              <ul className="grid max-h-80 grid-cols-[repeat(auto-fill,minmax(2.6rem,1fr))] gap-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
                {chapters.map((chapter) => {
                  const owner = linkOf(chapter);
                  return (
                    <li key={chapter}>
                      <button
                        type="button"
                        disabled={owner !== undefined}
                        onClick={(event) => {
                          choose(chapter, event.shiftKey || (from !== null && to === null && chapter > from));
                        }}
                        title={owner === undefined ? undefined : texts.chapters.inVolume(owner.volume)}
                        className={`w-full rounded py-1 text-[11px] tabular-nums ${
                          owner !== undefined
                            ? toneOf(owner)
                            : inRange(chapter)
                              ? "bg-accent text-white"
                              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        }`}
                      >
                        {chapterLabel(chapter)}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>

          <aside className="space-y-4">
            <h3 className="text-sm font-semibold">{texts.chapters.volumes}</h3>
            {links.length === 0 ? (
              <p className="rounded-lg bg-band px-4 py-6 text-center text-sm text-slate-500">{texts.chapters.none}</p>
            ) : (
              <ul className="space-y-2">
                {links.map((entry) => {
                  const count = presentOf(entry).length;
                  const missing = missingOf(entry);
                  const already = existing.includes(entry.volume);
                  return (
                    <li key={entry.volume} className="flex gap-3 rounded-lg border border-slate-200 p-2.5">
                      <span
                        aria-hidden="true"
                        className={`flex h-16 w-11 shrink-0 items-end rounded p-1 text-[10px] font-semibold ${toneOf(entry)}`}
                      >
                        T{String(entry.volume).padStart(2, "0")}
                      </span>
                      <span className="min-w-0 flex-1 text-sm">
                        <span className="flex items-center justify-between gap-2">
                          <span className="font-medium">{texts.chapters.volumeName(entry.volume)}</span>
                          <button
                            type="button"
                            onClick={() => {
                              setLinks(links.filter((other) => other !== entry));
                            }}
                            aria-label={texts.chapters.unlink(entry.volume)}
                            className="rounded px-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                          >
                            ×
                          </button>
                        </span>
                        <span className="block text-xs text-slate-500 tabular-nums">
                          {texts.chapters.range(chapterLabel(entry.from), chapterLabel(entry.to), count)}
                        </span>
                        {missing.length === 0 ? (
                          <>
                            <span className="mt-1 inline-block rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">
                              {texts.chapters.complete}
                            </span>
                            <span className="block text-xs text-slate-500">{texts.chapters.cover}</span>
                          </>
                        ) : (
                          <>
                            <span className="mt-1 inline-block rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800">
                              {texts.chapters.incomplete(missing.length, missingLabel(missing))}
                            </span>
                            <span className="block text-xs text-slate-500">{texts.chapters.loose(entry.volume)}</span>
                          </>
                        )}
                        {already ? (
                          <label className="mt-1 flex items-center gap-1.5 text-xs text-amber-800">
                            <input
                              type="checkbox"
                              checked={replace.has(entry.volume)}
                              onChange={(event) => {
                                const next = new Set(replace);
                                if (event.target.checked) {
                                  next.add(entry.volume);
                                } else {
                                  next.delete(entry.volume);
                                }
                                setReplace(next);
                              }}
                              className="size-3.5 accent-accent"
                            />
                            {texts.chapters.existing}
                          </label>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
            {free.length === 0 ? null : (
              <fieldset className="space-y-1.5 rounded-lg bg-band px-4 py-3 text-sm">
                <legend className="sr-only">{texts.chapters.restTitle}</legend>
                <p className="text-xs text-slate-500">
                  {texts.chapters.rest(free.length, chapterLabel(free[0] ?? 0), chapterLabel(free.at(-1) ?? 0))}
                </p>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="rest"
                    checked={rest === "place"}
                    onChange={() => {
                      setRest("place");
                    }}
                    className="accent-accent"
                  />
                  {texts.chapters.restPlace}
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="rest"
                    checked={rest === "keep"}
                    onChange={() => {
                      setRest("keep");
                    }}
                    className="accent-accent"
                  />
                  {texts.chapters.restKeep}
                </label>
              </fieldset>
            )}
            {existing.length === 0 ? null : (
              <p className="text-xs text-slate-500">
                {texts.chapters.library(existing.length, String(existing[0] ?? 1), String(existing.at(-1) ?? 1))}
              </p>
            )}
          </aside>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {refused ? (
            <span role="alert" className="text-sm text-rose-700">
              {texts.place.errors.refused}
            </span>
          ) : (
            <span className="text-sm text-slate-500">{texts.chapters.summary(complete.length, looseCount)}</span>
          )}
          <span className="flex gap-2">
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
              disabled={pick === null || complete.length + looseCount === 0 || pending}
              onClick={() => {
                void place();
              }}
              className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? <Spinner /> : null}
              {pending ? texts.place.moving : texts.chapters.place}
            </button>
          </span>
        </div>
      </div>
    </dialog>
  );
}
