// Les téléchargements de la page, lus dans l'API : au chargement, à l'arrivée sur la page, à la
// demande, et en temps réel quand il est actif.
import { useEffect, useState } from "react";

import type { Download } from "../types";
import { readDownloads } from "./downloads";

type Read = { readonly downloads: readonly Download[]; readonly at: Date };

export type DownloadsList = {
  /** null avant la première réponse. */
  readonly downloads: readonly Download[] | null;
  readonly updatedAt: Date;
  readonly refreshing: boolean;
  readonly refresh: () => void;
  /** Les téléchargements créés ou renvoyés, en tête ou à leur place. */
  readonly merge: (changed: readonly Download[]) => void;
};

/**
 * `active` : connecté (la barre latérale compte les téléchargements en cours). `shown` : la page
 * Téléchargements est ouverte ; `live` la relit toutes les `every` secondes.
 */
export function useDownloads(active: boolean, shown: boolean, live: boolean, every: number): DownloadsList {
  const [read, setRead] = useState<Read | null>(null);
  const [startedAt] = useState(() => new Date());
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    let current = true;
    function load(): void {
      readDownloads().then(
        (downloads) => {
          if (current) {
            setRead({ downloads, at: new Date() });
          }
        },
        () => undefined,
      );
    }
    load();
    const timer = shown && live ? window.setInterval(load, every * 1000) : undefined;
    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [active, shown, live, every]);

  function refresh(): void {
    setRefreshing(true);
    readDownloads().then(
      (downloads) => {
        setRead({ downloads, at: new Date() });
        setRefreshing(false);
      },
      () => {
        setRefreshing(false);
      },
    );
  }

  function merge(changed: readonly Download[]): void {
    setRead((current) => {
      const known = current?.downloads ?? [];
      const replaced = known.map((download) => changed.find((item) => item.id === download.id) ?? download);
      const added = changed.filter((download) => !known.some((item) => item.id === download.id));
      return { downloads: [...added, ...replaced], at: current?.at ?? new Date() };
    });
  }

  return {
    downloads: read?.downloads ?? null,
    updatedAt: read?.at ?? startedAt,
    refreshing,
    refresh,
    merge,
  };
}
