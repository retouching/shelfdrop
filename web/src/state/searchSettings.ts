// Paramètres › Recherche et Filtres : lus dans l'API, modifiés sur la page, enregistrés par le bouton
// « Enregistrer » de Paramètres.
import { useSyncExternalStore } from "react";

import {
  readFilters,
  readTrackers,
  refreshTrackers,
  saveFilters,
  saveTrackers,
  type FilterRule,
  type Tracker,
} from "../api/settings";

/** Une règle telle que la page la modifie : un identifiant local pour les listes React. */
export type EditableRule = FilterRule & { readonly id: string };

export type EditableFilters = { readonly rules: readonly EditableRule[]; readonly minimum: number };

type State = {
  readonly trackers: readonly Tracker[] | null;
  readonly filters: EditableFilters | null;
  readonly trackersChanged: boolean;
  readonly filtersChanged: boolean;
};

let state: State = { trackers: null, filters: null, trackersChanged: false, filtersChanged: false };
let nextId = 0;
const listeners = new Set<() => void>();

function publish(next: State): void {
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

export function useSearchSettings(): State {
  return useSyncExternalStore(subscribe, () => state);
}

export function newRuleId(): string {
  nextId += 1;
  return `rule-${String(nextId)}`;
}

function editable(rules: readonly FilterRule[]): readonly EditableRule[] {
  return rules.map((rule) => ({ ...rule, id: newRuleId() }));
}

/** Lit les trackers et les filtres enregistrés, sauf ce qui a été modifié sur la page. */
export async function loadSearchSettings(): Promise<void> {
  const [trackers, filters] = await Promise.all([readTrackers(), readFilters()]);
  publish({
    ...state,
    trackers: state.trackersChanged ? state.trackers : trackers,
    filters: state.filtersChanged ? state.filters : { rules: editable(filters.rules), minimum: filters.minimum },
  });
}

/** Relit les indexeurs de Prowlarr ; les choix enregistrés sont gardés. */
export async function rereadTrackers(): Promise<void> {
  publish({ ...state, trackers: await refreshTrackers(), trackersChanged: false });
}

export function setTrackers(trackers: readonly Tracker[]): void {
  publish({ ...state, trackers, trackersChanged: true });
}

export function setFilters(filters: EditableFilters): void {
  publish({ ...state, filters, filtersChanged: true });
}

/** Enregistre ce qui a été modifié ; une règle refusée par le serveur laisse la page telle quelle. */
export async function saveSearchSettings(): Promise<void> {
  const { trackers, filters, trackersChanged, filtersChanged } = state;
  if (trackersChanged && trackers !== null) {
    publish({ ...state, trackers: await saveTrackers(trackers), trackersChanged: false });
  }
  if (filtersChanged && filters !== null) {
    const saved = await saveFilters({
      minimum: filters.minimum,
      rules: filters.rules.map((rule) => ({
        name: rule.name,
        pattern: rule.pattern,
        regex: rule.regex,
        score: rule.score,
        kinds: rule.kinds,
        enabled: rule.enabled,
      })),
    });
    publish({ ...state, filters: { rules: editable(saved.rules), minimum: saved.minimum }, filtersChanged: false });
  }
}
