import { useEffect, useRef, useState, type ReactElement } from "react";

import { mergeWorks } from "../api/works";
import { texts } from "../texts";
import type { AltTitle, Kind, Work } from "../types";
import { Spinner } from "./Skeletons";
import { field, WorkPicker } from "./WorkPicker";
import { dialogBody, dialogFrame } from "./dialog";

type Props = {
  readonly kind: Kind;
  readonly work: Work;
  readonly onClose: () => void;
  readonly onMerged: () => void;
};

/** Les noms de toutes les œuvres, chacun une fois. */
export function unionTitles(works: readonly Work[]): readonly AltTitle[] {
  const seen = new Set<string>();
  return works
    .flatMap((entry) => entry.titles)
    .filter((alt) => {
      const key = alt.title.toLowerCase();
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

export function MergeDialog({ kind, work, onClose, onMerged }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [others, setOthers] = useState<readonly Work[]>([]);
  const [shelfName, setShelfName] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const members = work.mergedFrom ?? [work];
  const titles = others.length === 0 ? [] : unionTitles([...members, ...others]);
  const french = titles.find((alt) => alt.language === "FR")?.title;
  const chosenName = shelfName ?? french ?? work.title;

  async function merge(): Promise<void> {
    if (others.length === 0) {
      return;
    }
    setPending(true);
    setFailed(false);
    try {
      await mergeWorks(kind, [work.id, ...others.map((other) => other.id)], chosenName);
    } catch {
      setPending(false);
      setFailed(true);
      return;
    }
    onMerged();
    ref.current?.close();
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="merge-title" className={dialogFrame.fit}>
      <div className={dialogBody.regular}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="merge-title" className="text-lg font-semibold">
            {texts.works.mergeTitle}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">
            {work.title} · {work.author} ·{" "}
            {work.mergedFrom === undefined ? work.source : texts.works.mergedFrom(work.mergedFrom.length)}
          </p>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6">
          <WorkPicker
            kind={kind}
            initialQuery={work.title}
            value={null}
            onChange={() => {
              setOthers([]);
            }}
            exclude={new Set(members.map((member) => member.id))}
            withName={false}
            picked={new Set(others.map((other) => other.id))}
            onToggle={(candidate) => {
              setShelfName(null);
              setOthers((current) =>
                current.some((other) => other.id === candidate.id)
                  ? current.filter((other) => other.id !== candidate.id)
                  : [...current, candidate],
              );
            }}
          />

          {others.length === 0 ? null : (
            <>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.place.shelfName}</span>
                <select
                  value={chosenName}
                  onChange={(event) => {
                    setShelfName(event.target.value);
                  }}
                  className={field}
                >
                  {titles.map((alt) => (
                    <option key={alt.title} value={alt.title}>
                      {alt.title} ({alt.language})
                    </option>
                  ))}
                </select>
              </label>
              <div className="rounded-lg bg-band px-4 py-3">
                <p className="text-xs text-slate-500">{texts.works.mergedNames}</p>
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {titles.map((alt) => (
                    <li key={alt.title} className="rounded bg-surface px-2 py-0.5 text-sm text-slate-700">
                      {alt.title} <span className="text-xs text-slate-500">{alt.language}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {failed ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.works.mergeFailed}
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
            disabled={others.length === 0 || pending}
            onClick={() => {
              void merge();
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending
              ? texts.works.merging
              : others.length === 0
                ? texts.works.merge
                : `${texts.works.merge} · ${texts.works.mergeChosen(others.length)}`}
          </button>
        </div>
      </div>
    </dialog>
  );
}
