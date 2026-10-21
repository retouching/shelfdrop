// Les recherches mises en attente : lues dans l'API, relues chaque minute tant qu'une page les montre.
import { useEffect, useSyncExternalStore } from "react";

import type { Kind } from "../types";
import { request } from "./http";

export type Wanted =
  | { readonly target: "any" }
  | { readonly target: "volume"; readonly volume: number }
  | { readonly target: "chapters"; readonly from: number; readonly to: number | null };

export type WaitingState = { readonly kind: "waiting" } | { readonly kind: "found"; readonly releases: number };

export type WaitingSearch = {
  readonly id: number;
  readonly workId: string | null;
  readonly title: string;
  readonly kind: Kind;
  readonly names: readonly string[];
  readonly wanted: Wanted;
  /** « T03 », « Ch. 233 et suivants », « Toute release ». */
  readonly detail: string;
  readonly state: WaitingState;
  readonly attempts: number;
  /** Secondes Unix. */
  readonly addedAt: number;
  readonly searchedAt: number | null;
  readonly nextSearchAt: number;
};

export type WaitingList = {
  readonly searches: readonly WaitingSearch[];
  /** Heures entre deux recherches. */
  readonly everyHours: number;
};

type WantedBody = {
  readonly target: "any" | "volume" | "chapters";
  readonly volume: number | null;
  readonly chapter_from: number | null;
  readonly chapter_to: number | null;
};

type WaitingRead = {
  readonly id: number;
  readonly work_id: string | null;
  readonly title: string;
  readonly kind: Kind;
  readonly names: readonly string[];
  readonly wanted: WantedBody;
  readonly label: string;
  readonly state: "waiting" | "found";
  readonly releases: number;
  readonly attempts: number;
  readonly created_at: number;
  readonly searched_at: number | null;
  readonly next_search_at: number;
};

function wantedOf(body: WantedBody): Wanted {
  switch (body.target) {
    case "any":
      return { target: "any" };
    case "volume":
      return { target: "volume", volume: body.volume ?? 0 };
    case "chapters":
      return { target: "chapters", from: body.chapter_from ?? 0, to: body.chapter_to };
  }
}

function wantedBody(wanted: Wanted): WantedBody {
  switch (wanted.target) {
    case "any":
      return { target: "any", volume: null, chapter_from: null, chapter_to: null };
    case "volume":
      return { target: "volume", volume: wanted.volume, chapter_from: null, chapter_to: null };
    case "chapters":
      return { target: "chapters", volume: null, chapter_from: wanted.from, chapter_to: wanted.to };
  }
}

function searchOf(read: WaitingRead): WaitingSearch {
  return {
    id: read.id,
    workId: read.work_id,
    title: read.title,
    kind: read.kind,
    names: read.names,
    wanted: wantedOf(read.wanted),
    detail: read.label,
    state: read.state === "found" ? { kind: "found", releases: read.releases } : { kind: "waiting" },
    attempts: read.attempts,
    addedAt: read.created_at,
    searchedAt: read.searched_at,
    nextSearchAt: read.next_search_at,
  };
}

let state: WaitingList | null = null;
const listeners = new Set<() => void>();

function publish(next: WaitingList): void {
  state = next;
  for (const listener of listeners) {
    listener();
  }
}

export async function reloadWaiting(): Promise<void> {
  const body = await request<{ readonly searches: readonly WaitingRead[]; readonly every_hours: number }>(
    "GET",
    "/v1/waiting",
  );
  publish({ searches: body.searches.map(searchOf), everyHours: body.every_hours });
}

// La liste est relue chaque minute : une recherche trouvée allume la pastille de la barre latérale.
const RELOAD_MS = 60_000;

/** La liste, lue tant que `enabled` (une session ouverte) ; null avant la première lecture. */
export function useWaiting(enabled: boolean): WaitingList | null {
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    reloadWaiting().catch(() => undefined);
    const timer = setInterval(() => {
      reloadWaiting().catch(() => undefined);
    }, RELOAD_MS);
    return () => {
      clearInterval(timer);
    };
  }, [enabled]);
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

export type WaitOrder = {
  readonly workId: string | null;
  readonly title: string;
  readonly author: string;
  readonly kind: Kind;
  readonly names: readonly string[];
  readonly wanted: readonly Wanted[];
};

/** Les recherches ajoutées, et le nombre de celles déjà en attente. */
export async function addWaiting(order: WaitOrder): Promise<{ readonly added: number; readonly skipped: number }> {
  const body = await request<{ readonly added: readonly WaitingRead[]; readonly skipped: number }>(
    "POST",
    "/v1/waiting",
    {
      work_id: order.workId,
      title: order.title,
      author: order.author,
      kind: order.kind,
      names: order.names,
      wanted: order.wanted.map(wantedBody),
    },
  );
  await reloadWaiting();
  return { added: body.added.length, skipped: body.skipped };
}

export async function searchWaitingNow(id: number): Promise<void> {
  await request<WaitingRead>("POST", `/v1/waiting/${String(id)}/search`);
  await reloadWaiting();
}

export async function removeWaiting(id: number): Promise<void> {
  const response = await fetch(`/api/v1/waiting/${String(id)}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) {
    throw new Error(response.statusText);
  }
  await reloadWaiting();
}

export async function saveInterval(hours: number): Promise<void> {
  await request("PUT", "/v1/settings", { values: { "waiting.interval_hours": hours } });
  await reloadWaiting();
}

/** Les tomes déjà rangés ou dans la bibliothèque de son type. */
export async function readOwned(kind: Kind, title: string, workId: string | null): Promise<readonly number[]> {
  const query = new URLSearchParams({ kind, title });
  if (workId !== null) {
    query.set("work_id", workId);
  }
  const body = await request<{ readonly volumes: readonly number[] }>("GET", `/v1/waiting/owned?${query.toString()}`);
  return body.volumes;
}
