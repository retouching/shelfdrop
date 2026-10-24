import { useEffect, useRef, useState, type ReactElement } from "react";

import { addWaiting, readOwned, useWaiting, type Wanted } from "../api/waiting";
import { texts } from "../texts";
import type { Kind, Work } from "../types";
import { Spinner } from "./Skeletons";
import { field, WorkPicker, type Pick } from "./WorkPicker";
import { dialogBody, dialogFrame } from "./dialog";

type Target = "any" | "volumes" | "chapters";

type Props = {
  readonly kind: Kind;
  /** L'œuvre ouverte ; sans elle, la fenêtre commence par la recherche d'œuvre. */
  readonly work: Work | null;
  /** Tomes déjà couverts par les releases affichées. */
  readonly foundVolumes: readonly number[];
  readonly onClose: () => void;
  readonly onAdded: (count: number) => void;
};

// Les noms cherchés : ceux de l'œuvre cochés, 10 au plus.
const MAX_NAMES = 10;

export function WaitDialog({ kind, work, foundVolumes, onClose, onAdded }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const waiting = useWaiting(true)?.searches ?? [];
  const [pick, setPick] = useState<Pick | null>(null);
  const chosen = work ?? pick?.work ?? null;
  const [ownedOf, setOwnedOf] = useState<{ readonly id: string; readonly volumes: ReadonlySet<number> } | null>(null);
  const ownedSet: ReadonlySet<number> = chosen !== null && ownedOf?.id === chosen.id ? ownedOf.volumes : new Set();
  const owned = Math.max(0, ...ownedSet);
  // Tomes connus des sources, puis quelques tomes à venir, plus ceux saisis à la main.
  const known = Math.max(chosen?.volumeCount ?? 0, owned);
  const [extra, setExtra] = useState<readonly number[]>([]);
  const [typed, setTyped] = useState("");
  const total = Math.max(known + 3, ...extra);
  const [target, setTarget] = useState<Target>(kind === "manga" ? "volumes" : "any");
  const [volumes, setVolumes] = useState<ReadonlySet<number>>(() => new Set());
  const [touched, setTouched] = useState(false);
  const [chapterFrom, setChapterFrom] = useState("");
  const [chapterTo, setChapterTo] = useState("");
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  useEffect(() => {
    if (chosen === null) {
      return undefined;
    }
    const run = { stopped: false };
    readOwned(kind, chosen.title, chosen.id)
      .then((volumes) => {
        if (!run.stopped) {
          setOwnedOf({ id: chosen.id, volumes: new Set(volumes) });
        }
      })
      .catch(() => undefined);
    return () => {
      run.stopped = true;
    };
  }, [kind, chosen]);

  const already = new Set(
    waiting.filter((entry) => entry.title === chosen?.title && entry.kind === kind).map((entry) => entry.detail),
  );
  // Par défaut : les tomes qui ne sont ni dans la bibliothèque, ni dans les releases trouvées.
  const proposed = new Set(
    Array.from({ length: total }, (_, i) => i + 1).filter(
      (n) => !ownedSet.has(n) && !foundVolumes.includes(n) && n <= Math.max(known, owned + 1),
    ),
  );
  const selected = touched ? volumes : proposed;
  const fromNumber = Number(chapterFrom.replace(",", "."));
  const toNumber = Number(chapterTo.replace(",", "."));
  const chaptersValid =
    chapterFrom !== "" && fromNumber > 0 && (chapterTo === "" || (toNumber >= fromNumber && Number.isFinite(toNumber)));

  const wanted: readonly { readonly detail: string; readonly wanted: Wanted }[] =
    chosen === null
      ? []
      : target === "any"
        ? [{ detail: texts.waiting.anything, wanted: { target: "any" } }]
        : target === "volumes"
          ? [...selected]
              .sort((a, b) => a - b)
              .map((n) => ({ detail: `T${String(n).padStart(2, "0")}`, wanted: { target: "volume", volume: n } }))
          : chaptersValid
            ? [
                {
                  detail:
                    chapterTo === ""
                      ? texts.waitDialog.chaptersFrom(String(fromNumber))
                      : texts.waitDialog.chaptersRange(String(fromNumber), String(toNumber)),
                  wanted: { target: "chapters", from: fromNumber, to: chapterTo === "" ? null : toNumber },
                },
              ]
            : [];
  const entries = wanted.map((entry) => entry.detail);
  const fresh = wanted.filter((entry) => !already.has(entry.detail));

  /** « 26 », « 26-30 », « 26, 28 » : des tomes pas encore dans les métadonnées. */
  function addTyped(): void {
    const numbers = typed
      .split(",")
      .flatMap((part) => {
        const [a, b] = part.split(/-|à/u).map((value) => Number(value.trim()));
        if (a === undefined || !Number.isInteger(a) || a < 1) {
          return [];
        }
        const end = b !== undefined && Number.isInteger(b) && b >= a ? Math.min(b, a + 50) : a;
        return Array.from({ length: end - a + 1 }, (_, i) => a + i);
      })
      .filter((n) => !ownedSet.has(n));
    if (numbers.length === 0) {
      return;
    }
    setExtra([...new Set([...extra, ...numbers])]);
    setVolumes(new Set([...selected, ...numbers]));
    setTouched(true);
    setTyped("");
  }

  function toggle(n: number): void {
    const next = new Set(selected);
    if (next.has(n)) {
      next.delete(n);
    } else {
      next.add(n);
    }
    setVolumes(next);
    setTouched(true);
  }

  async function add(): Promise<void> {
    if (chosen === null || fresh.length === 0) {
      return;
    }
    setPending(true);
    setFailed(false);
    const names = [
      ...new Set([chosen.title, ...chosen.titles.filter((t) => t.checked !== false).map((t) => t.title)]),
    ].slice(0, MAX_NAMES);
    try {
      const result = await addWaiting({
        workId: chosen.id,
        title: chosen.title,
        author: chosen.author,
        kind,
        names,
        wanted: fresh.map((entry) => entry.wanted),
      });
      onAdded(result.added);
      ref.current?.close();
    } catch {
      setFailed(true);
      setPending(false);
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="wait-title" className={dialogFrame.fit}>
      <div className={dialogBody.regular}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="wait-title" className="text-lg font-semibold">
            {texts.waitDialog.title}
          </h2>
          {work === null ? null : (
            <p className="mt-0.5 text-sm text-slate-500">
              {work.title} · {work.author}
            </p>
          )}
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6">
          {work === null ? (
            <WorkPicker kind={kind} initialQuery="" value={pick} onChange={setPick} withName={false} />
          ) : null}

          {chosen === null ? null : (
            <>
              <div
                role="radiogroup"
                aria-label={texts.waitDialog.what}
                className="inline-flex rounded-lg bg-slate-100 p-1"
              >
                {(kind === "manga" ? (["volumes", "chapters", "any"] as const) : (["any", "volumes"] as const)).map(
                  (option) => (
                    <button
                      key={option}
                      type="button"
                      role="radio"
                      aria-checked={option === target}
                      onClick={() => {
                        setTarget(option);
                      }}
                      className={
                        option === target
                          ? "rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-ink shadow-sm"
                          : "rounded-md px-3 py-1.5 text-sm text-slate-500 hover:text-ink"
                      }
                    >
                      {texts.waitDialog.targets[option]}
                    </button>
                  ),
                )}
              </div>

              {target === "volumes" ? (
                <div className="space-y-2">
                  <ul className="grid grid-cols-[repeat(auto-fill,minmax(3.2rem,1fr))] gap-1.5">
                    {Array.from({ length: total }, (_, i) => i + 1).map((n) => {
                      const inLibrary = ownedSet.has(n);
                      const found = foundVolumes.includes(n);
                      const unknown = n > known;
                      const active = selected.has(n);
                      return (
                        <li key={n}>
                          <button
                            type="button"
                            aria-pressed={active}
                            disabled={inLibrary}
                            title={
                              inLibrary
                                ? texts.waitDialog.inLibrary
                                : found
                                  ? texts.waitDialog.found
                                  : unknown
                                    ? texts.waitDialog.unknown
                                    : undefined
                            }
                            onClick={() => {
                              toggle(n);
                            }}
                            className={`w-full rounded-md py-1.5 text-xs tabular-nums ${
                              inLibrary
                                ? "bg-emerald-50 text-emerald-700"
                                : active
                                  ? "bg-accent text-white"
                                  : found
                                    ? "bg-sky-50 text-sky-800 ring-1 ring-sky-200 ring-inset hover:bg-sky-100"
                                    : unknown
                                      ? "border border-dashed border-slate-300 text-slate-500 hover:bg-slate-50"
                                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                            }`}
                          >
                            T{String(n).padStart(2, "0")}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span>
                      <span className="mr-1 inline-block size-2.5 rounded-sm bg-emerald-200" />
                      {texts.waitDialog.inLibrary}
                    </span>
                    <span>
                      <span className="mr-1 inline-block size-2.5 rounded-sm bg-sky-200" />
                      {texts.waitDialog.found}
                    </span>
                    <span>
                      <span className="mr-1 inline-block size-2.5 rounded-sm bg-accent" />
                      {texts.waitDialog.chosen}
                    </span>
                    <span>
                      <span className="mr-1 inline-block size-2.5 rounded-sm border border-dashed border-slate-400" />
                      {texts.waitDialog.unknown}
                    </span>
                  </p>
                  <div className="flex items-end gap-2 pt-1">
                    <label className="block flex-1 space-y-1.5">
                      <span className="text-sm font-medium">{texts.waitDialog.other}</span>
                      <input
                        value={typed}
                        placeholder="26-30"
                        onChange={(event) => {
                          setTyped(event.target.value.replace(/[^\d,\- à]/gu, ""));
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            addTyped();
                          }
                        }}
                        className={field}
                      />
                    </label>
                    <button
                      type="button"
                      disabled={typed.trim() === ""}
                      onClick={addTyped}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                      {texts.waitDialog.addVolumes}
                    </button>
                  </div>
                  <p className="text-xs text-slate-500">{texts.waitDialog.otherHint(known)}</p>
                </div>
              ) : null}

              {target === "chapters" ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block space-y-1.5">
                    <span className="text-sm font-medium">{texts.waitDialog.from}</span>
                    <input
                      value={chapterFrom}
                      inputMode="decimal"
                      onChange={(event) => {
                        setChapterFrom(event.target.value.replace(/[^\d.,]/gu, ""));
                      }}
                      className={field}
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-sm font-medium">{texts.waitDialog.to}</span>
                    <input
                      value={chapterTo}
                      inputMode="decimal"
                      onChange={(event) => {
                        setChapterTo(event.target.value.replace(/[^\d.,]/gu, ""));
                      }}
                      className={field}
                    />
                    <span className="block text-xs text-slate-500">{texts.waitDialog.toHint}</span>
                  </label>
                </div>
              ) : null}

              {entries.length === 0 ? null : (
                <div className="rounded-lg bg-band px-4 py-3">
                  <p className="text-xs text-slate-500">{texts.waitDialog.preview}</p>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {entries.map((detail) => (
                      <li
                        key={detail}
                        className={`rounded px-2 py-0.5 text-sm ${
                          already.has(detail) ? "bg-slate-100 text-slate-400 line-through" : "bg-surface text-slate-700"
                        }`}
                        title={already.has(detail) ? texts.waitDialog.already : undefined}
                      >
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {failed ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.waitDialog.failed}
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
            disabled={fresh.length === 0 || pending}
            onClick={() => {
              void add();
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {texts.waitDialog.add(fresh.length)}
          </button>
        </div>
      </div>
    </dialog>
  );
}
