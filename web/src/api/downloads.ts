// Téléchargements : envoi des releases à qBittorrent, suivi, nouvel envoi.
import type { Download, DownloadState, Kind, Volumes } from "../types";
import { volumesLabel } from "../utils/volumes";
import { request } from "./http";

type VolumesBody = {
  readonly kind: "single" | "range" | "complete" | "unknown";
  readonly first: number | null;
  readonly last: number | null;
};

type ProgressRead = {
  readonly state: "downloading" | "waiting" | "placing" | "to_place" | "failed";
  readonly percent: number | null;
  readonly speed: number | null;
  readonly eta: number | null;
  readonly reason: "not_received" | "duplicate" | null;
};

type DownloadRead = {
  readonly id: number;
  readonly title: string;
  readonly mode: "auto" | "manual";
  readonly kind: Kind;
  readonly work_name: string;
  readonly series: string;
  readonly volumes: VolumesBody;
  readonly progress: ProgressRead;
  /** Secondes Unix. */
  readonly created_at: number;
};

type DownloadsRead = { readonly downloads: readonly DownloadRead[] };

export type SendRequest = {
  readonly searchId: string;
  readonly workId: string | null;
  readonly author: string;
  readonly series: string;
  readonly releases: readonly { readonly id: string; readonly volumes: Volumes }[];
};

function volumesBody(volumes: Volumes): VolumesBody {
  switch (volumes.kind) {
    case "single":
      return { kind: "single", first: volumes.number, last: volumes.number };
    case "range":
      return { kind: "range", first: volumes.from, last: volumes.to };
    case "complete":
    case "unknown":
      return { kind: volumes.kind, first: null, last: null };
  }
}

function volumesOf(read: VolumesBody): Volumes {
  if (read.kind === "single" && read.first !== null) {
    return { kind: "single", number: read.first };
  }
  if (read.kind === "range" && read.first !== null && read.last !== null) {
    return { kind: "range", from: read.first, to: read.last };
  }
  return read.kind === "complete" ? { kind: "complete" } : { kind: "unknown" };
}

function stateOf(read: ProgressRead): DownloadState {
  switch (read.state) {
    case "downloading":
      return { kind: "downloading", percent: read.percent ?? 0, speed: read.speed ?? 0, eta: read.eta ?? 0 };
    case "waiting":
      return { kind: "waiting" };
    case "placing":
      return { kind: "placing" };
    case "to_place":
      return { kind: "toPlace" };
    case "failed":
      return { kind: "failed", reason: read.reason ?? "not_received" };
  }
}

/** « Chainsaw Man - T01 à T11 » pour un téléchargement d'une œuvre, le nom de la release sinon. */
function downloadOf(read: DownloadRead): Download {
  const series = read.series === "" ? read.work_name : read.series;
  return {
    id: String(read.id),
    label: read.mode === "manual" ? read.title : `${series} - ${volumesLabel(volumesOf(read.volumes))}`,
    kind: read.kind,
    state: stateOf(read.progress),
    addedAt: new Date(read.created_at * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    workTitle: read.work_name,
    manual: read.mode === "manual",
  };
}

export async function readDownloads(): Promise<readonly Download[]> {
  return (await request<DownloadsRead>("GET", "/v1/downloads")).downloads.map(downloadOf);
}

export async function sendDownloads(send: SendRequest): Promise<readonly Download[]> {
  const body = {
    search_id: send.searchId,
    work_id: send.workId,
    author: send.author,
    series: send.series,
    releases: send.releases.map((release) => ({ id: release.id, volumes: volumesBody(release.volumes) })),
  };
  return (await request<DownloadsRead>("POST", "/v1/downloads", body)).downloads.map(downloadOf);
}

export async function retryDownload(id: string): Promise<Download> {
  return downloadOf(await request<DownloadRead>("POST", `/v1/downloads/${encodeURIComponent(id)}/retry`));
}
