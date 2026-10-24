// Paramètres de la recherche : trackers lus dans Prowlarr, filtres et score minimum.
import type { Kind } from "../types";
import { request } from "./http";

/** Une catégorie de l'indexeur dans Prowlarr ; une sous-catégorie porte le nom de son parent. */
export type TrackerCategory = {
  readonly id: number;
  readonly name: string;
};

/** Catégories cherchées pour chaque type ; aucune : l'indexeur n'est pas interrogé pour ce type. */
export type KindCategories = Readonly<Record<Kind, readonly number[]>>;

export type Tracker = {
  readonly indexer_id: number;
  readonly name: string;
  readonly language: string | null;
  /** Actif dans Prowlarr : un indexeur coupé là-bas n'est pas proposé. */
  readonly prowlarr_enabled: boolean;
  /** Interrogé par shelfdrop. */
  readonly used: boolean;
  /** Autorisé pour les téléchargements automatiques. */
  readonly auto: boolean;
  /** Catégories lues dans Prowlarr à la dernière lecture des indexeurs. */
  readonly available_categories: readonly TrackerCategory[];
  readonly categories: KindCategories;
  /** Jamais choisies : celles par défaut. */
  readonly default_categories: boolean;
};

export type FilterRule = {
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

type TrackersRead = { readonly trackers: readonly Tracker[] };

export async function readTrackers(): Promise<readonly Tracker[]> {
  return (await request<TrackersRead>("GET", "/v1/trackers")).trackers;
}

export async function refreshTrackers(): Promise<readonly Tracker[]> {
  return (await request<TrackersRead>("POST", "/v1/trackers/refresh")).trackers;
}

export async function saveTrackers(trackers: readonly Tracker[]): Promise<readonly Tracker[]> {
  const body = {
    trackers: trackers.map((tracker) => ({
      indexer_id: tracker.indexer_id,
      used: tracker.used,
      auto: tracker.auto,
      // Celles par défaut restent par défaut tant qu'elles ne sont pas changées.
      categories: tracker.default_categories ? null : tracker.categories,
    })),
  };
  return (await request<TrackersRead>("PUT", "/v1/trackers", body)).trackers;
}

export function readFilters(): Promise<FilterSettings> {
  return request<FilterSettings>("GET", "/v1/filters");
}

export function saveFilters(filters: FilterSettings): Promise<FilterSettings> {
  return request<FilterSettings>("PUT", "/v1/filters", filters);
}

/** Une valeur des paramètres : adresse, nombre ou interrupteur. */
export type SettingValue = string | number | boolean | null;

export type SettingsRead = {
  readonly values: Readonly<Record<string, SettingValue>>;
  /** Date de définition de chaque secret (secondes Unix), ou null : jamais sa valeur. */
  readonly secrets: Readonly<Record<string, number | null>>;
  /** Les clients torrent que cette version sait utiliser. */
  readonly torrent_clients: readonly string[];
};

export type SettingsUpdate = {
  readonly values: Readonly<Record<string, SettingValue>>;
  /** Nouvelle valeur, ou null pour effacer. */
  readonly secrets: Readonly<Record<string, string | null>>;
};

export type ProbeState =
  | "connected"
  | "no_address"
  | "no_key"
  | "refused"
  | "unavailable"
  /** Le client torrent répond, mais shelfdrop ne peut pas lui envoyer : `reason` dit pourquoi. */
  | "unsupported"
  /** Aucun connecteur de cette version pour le client torrent choisi. */
  | "no_connector";

export type ProbeRead = {
  readonly service: string;
  readonly ok: boolean;
  readonly state: ProbeState;
  readonly status: number | null;
  readonly version: string | null;
  readonly count: number | null;
  readonly missing: readonly string[];
  readonly elapsed_ms: number | null;
  /** Le client torrent testé ; null pour les autres services. */
  readonly client: string | null;
  /** `unsupported` : `label-plugin`, `transmission-version`… */
  readonly reason: string | null;
};

export type ProbeBody = {
  readonly service: string;
  /** Adresse saisie ; null : celle enregistrée. */
  readonly url: string | null;
  /** Clé saisie (le mot de passe d'un client torrent autre que qui) ; null : celle enregistrée ; "" : aucune. */
  readonly secret: string | null;
  /** Client torrent saisi ; null : celui enregistré. */
  readonly client?: string | null;
  /** Identifiant du client torrent saisi ; null : celui enregistré ; "" : aucun. */
  readonly username?: string | null;
};

type HealthRead = { readonly services: readonly ProbeRead[]; readonly checked_at: number | null };

export function readSettings(): Promise<SettingsRead> {
  return request<SettingsRead>("GET", "/v1/settings");
}

export function saveSettings(update: SettingsUpdate): Promise<SettingsRead> {
  return request<SettingsRead>("PUT", "/v1/settings", update);
}

export function testConnection(body: ProbeBody): Promise<ProbeRead> {
  return request<ProbeRead>("POST", "/v1/settings/test", body);
}

export async function readHealth(): Promise<readonly ProbeRead[]> {
  return (await request<HealthRead>("GET", "/v1/settings/health")).services;
}
