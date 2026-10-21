// Paramètres de la recherche : trackers lus dans Prowlarr, filtres et score minimum.
import type { Kind } from "../types";
import { request } from "./http";

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
    trackers: trackers.map((tracker) => ({ indexer_id: tracker.indexer_id, used: tracker.used, auto: tracker.auto })),
  };
  return (await request<TrackersRead>("PUT", "/v1/trackers", body)).trackers;
}

export function readFilters(): Promise<FilterSettings> {
  return request<FilterSettings>("GET", "/v1/filters");
}

export function saveFilters(filters: FilterSettings): Promise<FilterSettings> {
  return request<FilterSettings>("PUT", "/v1/filters", filters);
}
