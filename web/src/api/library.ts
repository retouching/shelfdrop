// La page Jellyfin : les séries des bibliothèques de Jellyfin, leurs propositions, leurs changements, les scans.
import type { Kind } from "../types";
import { request } from "./http";

export type Series = {
  readonly id: string;
  readonly kind: Kind;
  readonly name: string;
  readonly originalTitle: string;
  readonly authors: readonly string[];
  readonly year: number | null;
  readonly genres: readonly string[];
  readonly summary: string;
  readonly hasImage: boolean;
  readonly volumes: number;
  readonly volumesWithoutSummary: number;
  readonly volumesWithoutImage: number;
};

/** L'image d'une série ou d'un tome, lue dans Jellyfin par l'API. */
export function itemImage(id: string, width = 400): string {
  return `/api/v1/library/items/${encodeURIComponent(id)}/image?width=${String(width)}`;
}

export type Proposals = {
  /** Les tomes qui ont une image dans Jellyfin. */
  readonly volumes: readonly { readonly itemId: string; readonly label: string }[];
  readonly covers: readonly { readonly source: string; readonly url: string }[];
  readonly summaries: readonly { readonly source: string; readonly text: string }[];
};

export type ImageChoice =
  | { readonly kind: "item"; readonly itemId: string }
  | { readonly kind: "url"; readonly url: string }
  | { readonly kind: "data"; readonly data: string };

export type SeriesChange = {
  readonly name: string;
  readonly originalTitle: string;
  readonly authors: readonly string[];
  readonly year: number | null;
  readonly genres: readonly string[];
  readonly summary: string;
  readonly lock: boolean;
  readonly summaryToVolumes: boolean;
  readonly image: ImageChoice | null;
  readonly imageToSeries: boolean;
  readonly imageToVolumes: boolean;
  readonly saveCover: boolean;
};

export type ScanMode = "new" | "missing" | "all";
/** L'avancement du scan de chaque bibliothèque, de 0 à 100 ; null au repos. */
export type ScanProgress = Partial<Record<Kind, number | null>>;

type SeriesRead = {
  readonly id: string;
  readonly kind: Kind;
  readonly name: string;
  readonly original_title: string;
  readonly authors: readonly string[];
  readonly year: number | null;
  readonly genres: readonly string[];
  readonly summary: string;
  readonly has_image: boolean;
  readonly volumes: number;
  readonly volumes_without_summary: number;
  readonly volumes_without_image: number;
};

function seriesOf(read: SeriesRead): Series {
  return {
    id: read.id,
    kind: read.kind,
    name: read.name,
    originalTitle: read.original_title,
    authors: read.authors,
    year: read.year,
    genres: read.genres,
    summary: read.summary,
    hasImage: read.has_image,
    volumes: read.volumes,
    volumesWithoutSummary: read.volumes_without_summary,
    volumesWithoutImage: read.volumes_without_image,
  };
}

export async function readSeries(): Promise<readonly Series[]> {
  const body = await request<{ readonly series: readonly SeriesRead[] }>("GET", "/v1/library/series");
  return body.series.map(seriesOf);
}

export async function readProposals(id: string): Promise<Proposals> {
  const body = await request<{
    readonly volumes: readonly { readonly item_id: string; readonly label: string }[];
    readonly covers: Proposals["covers"];
    readonly summaries: Proposals["summaries"];
  }>("GET", `/v1/library/series/${encodeURIComponent(id)}/proposals`);
  return {
    volumes: body.volumes.map((volume) => ({ itemId: volume.item_id, label: volume.label })),
    covers: body.covers,
    summaries: body.summaries,
  };
}

function imageBody(image: ImageChoice | null): object | null {
  if (image === null) {
    return null;
  }
  switch (image.kind) {
    case "item":
      return { kind: "item", item_id: image.itemId };
    case "url":
      return { kind: "url", url: image.url };
    case "data":
      return { kind: "data", data: image.data };
  }
}

export async function changeSeries(id: string, change: SeriesChange): Promise<Series> {
  const read = await request<SeriesRead>("PUT", `/v1/library/series/${encodeURIComponent(id)}`, {
    name: change.name,
    original_title: change.originalTitle,
    authors: change.authors,
    year: change.year,
    genres: change.genres,
    summary: change.summary,
    lock: change.lock,
    summary_to_volumes: change.summaryToVolumes,
    image: imageBody(change.image),
    image_to_series: change.imageToSeries,
    image_to_volumes: change.imageToVolumes,
    save_cover: change.saveCover,
  });
  return seriesOf(read);
}

export async function fillSummaries(summaries: Readonly<Record<string, string>>): Promise<number> {
  const body = await request<{ readonly series: number }>("POST", "/v1/library/summaries", { summaries });
  return body.series;
}

export async function startScan(
  mode: ScanMode,
  target: { readonly kind?: Kind; readonly seriesId?: string } = {},
): Promise<ScanProgress> {
  const body = await request<{ readonly progress: ScanProgress }>("POST", "/v1/library/scan", {
    mode,
    kind: target.kind ?? null,
    series_id: target.seriesId ?? null,
  });
  return body.progress;
}

export async function readScan(): Promise<ScanProgress> {
  const body = await request<{ readonly progress: ScanProgress }>("GET", "/v1/library/scan");
  return body.progress;
}

/** Le contenu d'un fichier en base64, pour l'envoyer comme image. */
export async function base64Of(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}
