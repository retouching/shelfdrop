// Maquette : les recherches mises en attente, relancées à intervalle régulier.
import { useSyncExternalStore } from "react";

import type { Kind } from "../types";

export type WaitingState =
  { readonly kind: "waiting" } | { readonly kind: "searching" } | { readonly kind: "found"; readonly releases: number };

export type WaitingSearch = {
  readonly id: string;
  readonly title: string;
  /** Ce qui manque : un tome, une édition, ou rien de précis. */
  readonly detail: string;
  readonly kind: Kind;
  readonly names: number;
  readonly addedAt: string;
  readonly lastSearch: string;
  readonly nextSearch: string;
  readonly attempts: number;
  readonly state: WaitingState;
};

let state: readonly WaitingSearch[] = [
  {
    id: "w1",
    title: "Ichi the Witch",
    detail: "T03",
    kind: "manga",
    names: 4,
    addedAt: "18/10",
    lastSearch: "16:00",
    nextSearch: "22:00",
    attempts: 12,
    state: { kind: "found", releases: 2 },
  },
  {
    id: "w2",
    title: "La Mémoire des os",
    detail: "T03",
    kind: "audiobook",
    names: 2,
    addedAt: "14/10",
    lastSearch: "16:00",
    nextSearch: "22:00",
    attempts: 29,
    state: { kind: "waiting" },
  },
  {
    id: "w3",
    title: "Bloom Into You",
    detail: "Anthologie",
    kind: "manga",
    names: 5,
    addedAt: "21/10",
    lastSearch: "16:00",
    nextSearch: "22:00",
    attempts: 1,
    state: { kind: "waiting" },
  },
];

const listeners = new Set<() => void>();

export function setWaiting(next: readonly WaitingSearch[]): void {
  state = next;
  for (const listener of listeners) {
    listener();
  }
}

export function useWaiting(): readonly WaitingSearch[] {
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
