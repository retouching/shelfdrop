// Maquette : les indexeurs lus dans Prowlarr, choisis et ordonnés dans Paramètres › Recherche.
import { useSyncExternalStore } from "react";

export type Tracker = {
  readonly name: string;
  /** Actif dans Prowlarr : un indexeur coupé là-bas n'est pas proposé. */
  readonly prowlarrEnabled: boolean;
  /** Interrogé par shelfdrop. */
  readonly used: boolean;
  /** Autorisé pour les téléchargements automatiques. */
  readonly auto: boolean;
  readonly language: string;
};

let state: readonly Tracker[] = [
  { name: "Nyaa.si", prowlarrEnabled: true, used: true, auto: true, language: "Multi" },
  { name: "The Old School", prowlarrEnabled: true, used: true, auto: true, language: "FR" },
  { name: "Abnormal", prowlarrEnabled: true, used: true, auto: true, language: "FR" },
  { name: "C411", prowlarrEnabled: true, used: true, auto: false, language: "FR" },
  { name: "YggTorrent", prowlarrEnabled: false, used: false, auto: false, language: "FR" },
  { name: "TorrentLeech", prowlarrEnabled: true, used: false, auto: false, language: "EN" },
];

const listeners = new Set<() => void>();

export function setTrackers(next: readonly Tracker[]): void {
  state = next;
  for (const listener of listeners) {
    listener();
  }
}

export function useTrackers(): readonly Tracker[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => state,
  );
}
