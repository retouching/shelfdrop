import { useEffect, useRef, useState, type ReactElement, type SubmitEvent } from "react";

import { sendDownloads } from "../api/downloads";
import { texts } from "../texts";
import type { Download, Kind, Release } from "../types";
import { Spinner } from "./Skeletons";
import { compareForDisplay, coverageLabel, parseVolumesInput, volumesInput } from "../utils/volumes";
import { dialogBody, dialogFrame } from "./dialog";

type Props = {
  readonly kind: Kind;
  /** La recherche des releases, et l'œuvre cherchée (aucune en manuel). */
  readonly searchId: string;
  readonly workId: string | null;
  readonly releases: readonly Release[];
  /** Recherche manuelle : pas d'auteur ni de série ici, l'association se fait dans Ranger. */
  readonly manual: boolean;
  readonly onClose: () => void;
  readonly onSent: (downloads: readonly Download[]) => void;
};

const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

export function DownloadDialog({ kind, searchId, workId, releases, manual, onClose, onSent }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const first = releases[0];
  const [author, setAuthor] = useState(first?.author ?? "");
  const [series, setSeries] = useState(first?.series ?? "");
  const [volumes, setVolumes] = useState<Readonly<Record<string, string>>>(() =>
    Object.fromEntries(releases.map((release) => [release.id, volumesInput(release.volumes)])),
  );

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const ordered = [...releases].sort(compareForDisplay);
  const coverage = coverageLabel(
    releases.map((release) => ({ ...release, volumes: parseVolumesInput(volumes[release.id] ?? "") })),
  );
  const library = texts.libraries[kind];
  const destination = kind === "manga" ? [library, series] : [library, author, series];

  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function send(): Promise<void> {
    setPending(true);
    setFailed(false);
    try {
      const sent = await sendDownloads({
        searchId,
        workId: manual ? null : workId,
        author: manual ? "" : author,
        series: manual ? "" : series,
        releases: releases.map((release) => ({
          id: release.id,
          volumes: parseVolumesInput(volumes[release.id] ?? ""),
        })),
      });
      onSent(sent);
    } catch {
      setPending(false);
      setFailed(true);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void send();
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="dialog-title" className={dialogFrame.fit}>
      <form onSubmit={submit} className={dialogBody.regular}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="dialog-title" className="text-lg font-semibold">
            {texts.dialog.title}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">{texts.dialog.summary(releases.length, coverage)}</p>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6">
          {manual ? (
            <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">{texts.dialog.manualNote}</p>
          ) : null}
          {manual ? null : (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.dialog.author}</span>
                <input
                  value={author}
                  onChange={(event) => {
                    setAuthor(event.target.value);
                  }}
                  className={field}
                />
              </label>
              <label className="block space-y-1.5">
                <span className="text-sm font-medium">{texts.dialog.series}</span>
                <input
                  value={series}
                  onChange={(event) => {
                    setSeries(event.target.value);
                  }}
                  className={field}
                />
              </label>
            </div>
          )}
          <fieldset>
            <legend className="text-sm font-medium">{texts.dialog.volumes}</legend>
            <p className="mt-0.5 text-xs text-slate-500">{texts.dialog.volumesHint}</p>
            <ul className="mt-2 max-h-60 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
              {ordered.map((release) => (
                <li key={release.id} className="flex items-center gap-3 px-3 py-2">
                  <input
                    value={volumes[release.id] ?? ""}
                    onChange={(event) => {
                      setVolumes({ ...volumes, [release.id]: event.target.value });
                    }}
                    aria-label={texts.dialog.releaseVolumes(release.title)}
                    inputMode="numeric"
                    className="w-20 rounded-md border border-slate-200 px-2 py-1 text-center text-sm outline-none focus:border-accent"
                  />
                  <span
                    className="min-w-0 flex-1 truncate text-sm text-slate-600 [contain:inline-size]"
                    title={release.title}
                  >
                    {release.title}
                  </span>
                </li>
              ))}
            </ul>
          </fieldset>
          {manual ? null : (
            <div className="rounded-lg bg-band px-4 py-3">
              <p className="text-xs text-slate-500">{texts.dialog.destination}</p>
              <p className="mt-1 text-sm font-medium">{destination.join(" › ")}</p>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {failed ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.dialog.failed}
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
            type="submit"
            disabled={pending}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.loading.sending : texts.dialog.submit}
          </button>
        </div>
      </form>
    </dialog>
  );
}
