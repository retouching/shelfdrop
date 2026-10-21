import type { ReactElement } from "react";

import type { NameProgress } from "../api/searches";
import { texts } from "../texts";
import { CheckIcon } from "./icons";
import { Spinner } from "./Skeletons";

type Props = {
  readonly workTitle: string;
  /** Les noms cherchés et leur état, tels que le serveur les envoie. */
  readonly names: readonly NameProgress[];
  /** Recherches devant celle-ci dans la file de Prowlarr. */
  readonly queuedAhead: number;
  /** Lancée aussi par quelqu'un d'autre : suivie ensemble. */
  readonly shared: boolean;
};

/** Chargement des releases : un état par nom cherché dans Prowlarr. */
export function ReleasesLoading({ workTitle, names, queuedAhead, shared }: Props): ReactElement {
  const finished = names.filter((name) => name.state === "done" || name.state === "failed").length;

  return (
    <section
      aria-busy="true"
      aria-labelledby="releases-loading-title"
      className="rounded-xl border border-slate-200 bg-surface px-6 py-8"
    >
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <Spinner className="size-8 text-accent-text" />
        <h2 id="releases-loading-title" className="mt-4 font-semibold text-ink">
          {texts.loading.releasesFor(workTitle)}
        </h2>
        <p role="status" className="mt-1 text-sm text-slate-500">
          {queuedAhead > 0 ? texts.loading.queued(queuedAhead) : texts.loading.namesProgress(finished, names.length)}
        </p>
        {shared ? <p className="mt-1 text-xs text-slate-500">{texts.loading.shared}</p> : null}
        <div aria-hidden="true" className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${String(Math.round((finished / Math.max(names.length, 1)) * 100))}%` }}
          />
        </div>
        <ul className="mt-5 w-full space-y-2 text-left text-sm">
          {names.map((name) => {
            const isDone = name.state === "done" || name.state === "failed";
            const isRunning = name.state === "running";
            return (
              <li key={name.name} className="flex items-center gap-2.5">
                {isDone ? (
                  <CheckIcon className="size-4 text-emerald-600" />
                ) : isRunning ? (
                  <Spinner className="size-4 text-accent-text" />
                ) : (
                  <span aria-hidden="true" className="size-4 rounded-full border border-slate-300" />
                )}
                <span className={isDone || isRunning ? "text-ink" : "text-slate-400"}>{name.name}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
