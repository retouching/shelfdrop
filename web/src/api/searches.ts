// Recherche de releases dans Prowlarr : lancement, avancement (Server-Sent Events), résultats.
import type { Kind, Release, Volumes } from "../types";
import { request } from "./http";

export type NameProgress = {
  readonly name: string;
  readonly state: "queued" | "running" | "done" | "failed";
  readonly found: number;
};

export type SearchProgress = {
  readonly id: string;
  readonly state: "queued" | "running" | "done" | "failed";
  readonly names: readonly NameProgress[];
  readonly queued_ahead: number;
  readonly followers: number;
  /** Secondes Unix : réponse de Prowlarr la plus ancienne (peut venir du cache). */
  readonly fetched_at: number | null;
};

type VolumesRead = {
  readonly kind: "single" | "range" | "complete" | "unknown";
  readonly first: number | null;
  readonly last: number | null;
};

type ReleaseRead = {
  readonly id: string;
  readonly title: string;
  readonly matched_name: string;
  readonly indexer: string;
  readonly indexer_rank: number;
  readonly info_url: string | null;
  readonly seeders: number;
  readonly size: number;
  readonly volumes: VolumesRead;
  readonly score: number;
  readonly score_rules: readonly { readonly name: string; readonly score: number }[];
  readonly rejected: "relevance" | "score" | null;
};

type ReleaseSearchRead = {
  readonly progress: SearchProgress;
  readonly releases: readonly ReleaseRead[];
  readonly minimum: number;
};

export type SearchResult = {
  readonly progress: SearchProgress;
  readonly releases: readonly Release[];
  readonly minimum: number;
};

export type SearchRequest = {
  readonly mode: "work" | "manual";
  readonly kind: Kind;
  readonly title: string;
  readonly names: readonly string[];
  readonly refresh: boolean;
};

function volumesOf(read: VolumesRead): Volumes {
  if (read.kind === "single" && read.first !== null) {
    return { kind: "single", number: read.first };
  }
  if (read.kind === "range" && read.first !== null && read.last !== null) {
    return { kind: "range", from: read.first, to: read.last };
  }
  return read.kind === "complete" ? { kind: "complete" } : { kind: "unknown" };
}

/** `author` et `series` préremplissent la fenêtre de téléchargement. */
function releaseOf(read: ReleaseRead, author: string, series: string): Release {
  return {
    id: read.id,
    title: read.title,
    matchedName: read.matched_name,
    infoUrl: read.info_url ?? "",
    indexer: read.indexer,
    indexerRank: read.indexer_rank,
    seeders: read.seeders,
    sizeBytes: read.size,
    author,
    series,
    volumes: volumesOf(read.volumes),
    score: read.score,
    scoreRules: read.score_rules,
    rejected: read.rejected,
  };
}

export function startSearch(search: SearchRequest): Promise<SearchProgress> {
  return request<SearchProgress>("POST", "/v1/searches", search);
}

export async function readSearch(id: string, author: string, series: string): Promise<SearchResult> {
  const found = await request<ReleaseSearchRead>("GET", `/v1/searches/${encodeURIComponent(id)}`);
  return {
    progress: found.progress,
    minimum: found.minimum,
    releases: found.releases.map((release) => releaseOf(release, author, series)),
  };
}

/** Suit l'avancement d'une recherche jusqu'à sa fin ; renvoie de quoi arrêter de suivre. */
export function followSearch(
  id: string,
  onProgress: (progress: SearchProgress) => void,
  onEnd: () => void,
): () => void {
  const source = new EventSource(`/api/v1/searches/${encodeURIComponent(id)}/events`);
  source.addEventListener("progress", (event) => {
    onProgress(JSON.parse((event as MessageEvent<string>).data) as SearchProgress);
  });
  const end = (): void => {
    source.close();
    onEnd();
  };
  source.addEventListener("end", end);
  source.addEventListener("error", end);
  return () => {
    source.close();
  };
}
