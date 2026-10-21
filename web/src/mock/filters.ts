// Maquette : les filtres de releases (mots ou regex, avec des points), gardés en mémoire le temps de la page.
import { useSyncExternalStore } from "react";

import type { Kind } from "../types";

export type FilterRule = {
  readonly id: string;
  readonly name: string;
  /** Mots séparés par des virgules (mots entiers, sans casse), ou une regex. */
  readonly pattern: string;
  readonly regex: boolean;
  readonly score: number;
  /** Types concernés ; vide = tous. */
  readonly kinds: readonly Kind[];
  readonly enabled: boolean;
};

export type FilterSettings = {
  readonly rules: readonly FilterRule[];
  /** Score sous lequel une release est écartée. */
  readonly minimum: number;
};

let state: FilterSettings = {
  minimum: -100,
  rules: [
    {
      id: "r1",
      name: "Français",
      pattern: String.raw`\b(FRENCH|TRUEFRENCH|VF|FR)\b`,
      regex: true,
      score: 100,
      kinds: [],
      enabled: true,
    },
    {
      id: "r2",
      name: "Pack de tomes",
      pattern: String.raw`\bT\d{2}-T\d{2}\b|Int[ée]grale`,
      regex: true,
      score: 25,
      kinds: ["manga"],
      enabled: true,
    },
    { id: "r3", name: "Numérique", pattern: "eBook, Digital", regex: false, score: 10, kinds: [], enabled: true },
    {
      id: "r4",
      name: "Couleur",
      pattern: "FullColor, Couleur",
      regex: false,
      score: -15,
      kinds: ["manga"],
      enabled: true,
    },
    {
      id: "r5",
      name: "Anglais",
      pattern: String.raw`\b(ENG|ENGLISH)\b|\(1r0n\)`,
      regex: true,
      score: -50,
      kinds: [],
      enabled: true,
    },
    { id: "r6", name: "Raw japonais", pattern: "RAW, JPN", regex: false, score: -200, kinds: ["manga"], enabled: true },
    {
      id: "r7",
      name: "MP3 128 kbit/s",
      pattern: String.raw`128\s?kbps`,
      regex: true,
      score: -5,
      kinds: ["audiobook"],
      enabled: true,
    },
  ],
};

const listeners = new Set<() => void>();

export function setFilters(next: FilterSettings): void {
  state = next;
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useFilters(): FilterSettings {
  return useSyncExternalStore(subscribe, () => state);
}
