// Paramètres enregistrés dans l'API (services, sources, recherche, journal Discord) : lus,
// modifiés sur la page, enregistrés par le bouton « Enregistrer » de Paramètres.
import { useSyncExternalStore } from "react";

import { readSettings, saveSettings, type SettingValue, type SettingsRead } from "../api/settings";
import { texts } from "../texts";
import type { TorrentClient } from "../types";

/** Modification d'un secret : une nouvelle valeur, ou null pour l'effacer. */
export type SecretEdit = string | null;

type State = {
  readonly saved: SettingsRead | null;
  readonly values: Readonly<Record<string, SettingValue>>;
  readonly secrets: Readonly<Record<string, SecretEdit>>;
};

let state: State = { saved: null, values: {}, secrets: {} };
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

export function useSettings(): State {
  return useSyncExternalStore(subscribe, () => state);
}

/** La valeur affichée : celle modifiée sur la page, sinon celle enregistrée. */
export function valueOf(current: State, key: string): SettingValue | undefined {
  return key in current.values ? current.values[key] : current.saved?.values[key];
}

export const torrentClients: readonly TorrentClient[] = ["qui", "qbittorrent", "deluge", "transmission"];

export function isTorrentClient(value: unknown): value is TorrentClient {
  return torrentClients.some((client) => client === value);
}

/** Le client torrent : celui choisi sur la page, sinon celui enregistré (`saved` : celui enregistré seul). */
export function torrentClientOf(current: State, saved = false): TorrentClient {
  const value = saved ? current.saved?.values["torrent.client"] : valueOf(current, "torrent.client");
  return isTorrentClient(value) ? value : "qui";
}

/** Le nom du client torrent enregistré, pour les messages des téléchargements. */
export function useTorrentClientName(): string {
  return texts.torrentClients[torrentClientOf(useSettings(), true)];
}

export async function loadSettings(): Promise<void> {
  publish({ ...state, saved: await readSettings() });
}

export function setValue(key: string, value: SettingValue): void {
  publish({ ...state, values: { ...state.values, [key]: value } });
}

/** `undefined` annule la modification du secret. */
export function setSecret(key: string, edit: SecretEdit | undefined): void {
  const secrets = Object.fromEntries(Object.entries(state.secrets).filter(([name]) => name !== key));
  publish({ ...state, secrets: edit === undefined ? secrets : { ...secrets, [key]: edit } });
}

/** Enregistre ce qui a été modifié ; un refus du serveur laisse la page telle quelle. */
export async function saveChangedSettings(): Promise<void> {
  const { values, secrets } = state;
  if (Object.keys(values).length === 0 && Object.keys(secrets).length === 0) {
    return;
  }
  // Un secret « Remplacer » laissé vide n'est pas une modification.
  const changed = Object.fromEntries(Object.entries(secrets).filter(([, edit]) => edit !== ""));
  publish({ saved: await saveSettings({ values, secrets: changed }), values: {}, secrets: {} });
}
