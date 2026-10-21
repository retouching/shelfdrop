import { useEffect, useState, type ReactElement } from "react";

import { texts } from "../texts";
import { CheckIcon } from "./icons";
import { Spinner } from "./Skeletons";

type Props = {
  readonly workTitle: string;
  readonly names: readonly string[];
  /** Maquette : délai simulé par nom. Le vrai serveur enverra l'avancement nom par nom. */
  readonly stepMs: number;
};

/** Chargement des releases : un état par nom cherché dans Prowlarr. */
export function ReleasesLoading({ workTitle, names, stepMs }: Props): ReactElement {
  const [done, setDone] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setDone((n) => n + 1);
    }, stepMs);
    return () => {
      window.clearInterval(timer);
    };
  }, [stepMs]);

  const finished = Math.min(done, names.length);

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
          {texts.loading.namesProgress(finished, names.length)}
        </p>
        <div aria-hidden="true" className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${String(Math.round((finished / Math.max(names.length, 1)) * 100))}%` }}
          />
        </div>
        <ul className="mt-5 w-full space-y-2 text-left text-sm">
          {names.map((name, index) => {
            const isDone = index < finished;
            const isRunning = index === finished;
            return (
              <li key={name} className="flex items-center gap-2.5">
                {isDone ? (
                  <CheckIcon className="size-4 text-emerald-600" />
                ) : isRunning ? (
                  <Spinner className="size-4 text-accent-text" />
                ) : (
                  <span aria-hidden="true" className="size-4 rounded-full border border-slate-300" />
                )}
                <span className={isDone || isRunning ? "text-ink" : "text-slate-400"}>{name}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
