// États de la page Rechercher, branchés sur l'API : œuvres trouvées, puis releases avec leur avancement.
import { useEffect, useState } from "react";

import type { Kind, Work } from "../types";
import { followSearch, readSearch, startSearch, type SearchProgress, type SearchResult } from "./searches";
import { searchWorks } from "./works";

export type WorksState =
  | { readonly status: "idle" }
  | { readonly status: "loading" }
  | { readonly status: "done"; readonly works: readonly Work[] };

type WorksAnswer = { readonly key: string; readonly works: readonly Work[] };

/** Les œuvres de `query` ; aucune recherche sans texte. `round` relance la même recherche. */
export function useWorks(query: string, kind: Kind, round: number, enabled: boolean): WorksState {
  const active = enabled && query.trim().length >= 2;
  const key = `${kind}|${query}|${String(round)}`;
  const [answer, setAnswer] = useState<WorksAnswer | null>(null);

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    let current = true;
    searchWorks(query, kind).then(
      (found) => {
        if (current) {
          setAnswer({ key, works: found.works });
        }
      },
      () => {
        // Aucune source ne répond : la liste reste vide, avec son message.
        if (current) {
          setAnswer({ key, works: [] });
        }
      },
    );
    return () => {
      current = false;
    };
  }, [active, key, query, kind]);

  if (!active) {
    return { status: "idle" };
  }
  return answer?.key === key ? { status: "done", works: answer.works } : { status: "loading" };
}

export type ReleasesState =
  | { readonly status: "idle" }
  | { readonly status: "running"; readonly progress: SearchProgress | null }
  | {
      readonly status: "done";
      readonly result: SearchResult;
      /** Âge des réponses de Prowlarr à l'arrivée des résultats, en minutes. */
      readonly ageMinutes: number | null;
    }
  | { readonly status: "unavailable" };

export type ReleasesQuery = {
  readonly mode: "work" | "manual";
  readonly kind: Kind;
  readonly title: string;
  readonly names: readonly string[];
  /** Préremplissage de la fenêtre de téléchargement. */
  readonly author: string;
  readonly series: string;
};

type Step =
  | { readonly key: string; readonly status: "running"; readonly progress: SearchProgress }
  | { readonly key: string; readonly status: "done"; readonly result: SearchResult; readonly ageMinutes: number | null }
  | { readonly key: string; readonly status: "unavailable" };

const SEPARATOR = "\u0000";

/**
 * La recherche de releases de `search` (null : aucune). L'avancement arrive nom par nom, puis les
 * releases à la fin. `round` au-dessus de 0 : la même recherche relancée sans le cache de Prowlarr.
 */
export function useReleases(search: ReleasesQuery | null, round: number): ReleasesState {
  const active = search !== null && search.names.length > 0;
  const mode = search?.mode ?? "manual";
  const kind = search?.kind ?? "manga";
  const title = search?.title ?? "";
  const names = search?.names.join(SEPARATOR) ?? "";
  const author = search?.author ?? "";
  const series = search?.series ?? "";
  const key = `${mode}|${kind}|${names}|${String(round)}`;
  const [step, setStep] = useState<Step | null>(null);

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    let current = true;
    let stop = (): void => undefined;
    const fail = (): void => {
      if (current) {
        setStep({ key, status: "unavailable" });
      }
    };
    const finish = (id: string): void => {
      readSearch(id, author, series).then((result) => {
        if (!current) {
          return;
        }
        const fetched = result.progress.fetched_at;
        const ageMinutes = fetched === null ? null : Math.max(0, Math.floor((Date.now() / 1000 - fetched) / 60));
        setStep(
          result.progress.state === "failed"
            ? { key, status: "unavailable" }
            : { key, status: "done", result, ageMinutes },
        );
      }, fail);
    };
    startSearch({ mode, kind, title, names: names.split(SEPARATOR), refresh: round > 0 }).then((progress) => {
      if (!current) {
        return;
      }
      setStep({ key, status: "running", progress });
      stop = followSearch(
        progress.id,
        (next) => {
          if (current) {
            setStep({ key, status: "running", progress: next });
          }
        },
        () => {
          finish(progress.id);
        },
      );
    }, fail);
    return () => {
      current = false;
      stop();
    };
  }, [active, key, mode, kind, title, names, author, series, round]);

  if (!active) {
    return { status: "idle" };
  }
  if (step?.key !== key) {
    return { status: "running", progress: null };
  }
  switch (step.status) {
    case "running":
      return { status: "running", progress: step.progress };
    case "done":
      return { status: "done", result: step.result, ageMinutes: step.ageMinutes };
    case "unavailable":
      return { status: "unavailable" };
  }
}
