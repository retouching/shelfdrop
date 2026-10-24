// La page Jellyfin : les séries des bibliothèques de Jellyfin, leurs propositions, leurs changements, les scans.
import type { Kind } from "../types";
import type { TitleProposal } from "../utils/titles";
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
  /** L'étiquette de son image dans Jellyfin, qui change avec elle ; null sans image. */
  readonly imageTag: string | null;
};

/**
 * L'image d'une série ou d'un tome, lue dans Jellyfin par l'API. Son étiquette fait partie de
 * l'adresse : le navigateur la garde, et une nouvelle image a une nouvelle adresse.
 */
export function itemImage(id: string, tag: string | null, width = 400): string {
  const versioned = tag === null ? "" : `&tag=${encodeURIComponent(tag)}`;
  return `/api/v1/library/items/${encodeURIComponent(id)}/image?width=${String(width)}${versioned}`;
}

/** L'œuvre d'où viennent les propositions d'une série. */
export type SeriesWork = {
  readonly id: string;
  readonly title: string;
  readonly shelfName: string;
  readonly authors: readonly string[];
  readonly year: number | null;
  readonly sources: readonly string[];
  /** L'adresse de sa couverture, servie par l'API ; null sans couverture. */
  readonly cover: string | null;
};

export type Proposals = {
  /** Les tomes qui ont une image dans Jellyfin. */
  readonly volumes: readonly { readonly itemId: string; readonly label: string; readonly imageTag: string | null }[];
  readonly covers: readonly { readonly source: string; readonly url: string }[];
  readonly summaries: readonly { readonly source: string; readonly text: string }[];
  /** L'œuvre choisie à la main (`linked`), sinon la première trouvée sous son nom ; null sans œuvre. */
  readonly work?: SeriesWork | null;
  readonly linked?: boolean;
  /** Les noms de l'œuvre : les propositions du titre. */
  readonly names?: readonly TitleProposal[];
};

type ProposalsRead = {
  readonly volumes: readonly {
    readonly item_id: string;
    readonly label: string;
    readonly image_tag: string | null;
  }[];
  readonly covers: Proposals["covers"];
  readonly summaries: Proposals["summaries"];
  readonly work: {
    readonly id: string;
    readonly title: string;
    readonly shelf_name: string;
    readonly authors: readonly string[];
    readonly year: number | null;
    readonly sources: readonly string[];
    readonly cover_url: string | null;
  } | null;
  readonly linked: boolean;
  readonly names: readonly TitleProposal[];
};

function proposalsOf(body: ProposalsRead): Proposals {
  const work = body.work;
  return {
    volumes: body.volumes.map((volume) => ({
      itemId: volume.item_id,
      label: volume.label,
      imageTag: volume.image_tag,
    })),
    covers: body.covers,
    summaries: body.summaries,
    work:
      work === null
        ? null
        : {
            id: work.id,
            title: work.title,
            shelfName: work.shelf_name,
            authors: work.authors,
            year: work.year,
            sources: work.sources,
            cover: work.cover_url === null ? null : `/api/v1/works/cover?id=${encodeURIComponent(work.id)}`,
          },
    linked: body.linked,
    names: body.names.map((name) => ({ title: name.title, language: name.language, sources: name.sources })),
  };
}

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
  readonly image_tag: string | null;
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
    imageTag: read.image_tag,
  };
}

export async function readSeries(): Promise<readonly Series[]> {
  const body = await request<{ readonly series: readonly SeriesRead[] }>("GET", "/v1/library/series");
  return body.series.map(seriesOf);
}

export async function readProposals(id: string): Promise<Proposals> {
  return proposalsOf(await request<ProposalsRead>("GET", `/v1/library/series/${encodeURIComponent(id)}/proposals`));
}

/** La série liée à une autre œuvre ; ses propositions relues. */
export async function linkWork(id: string, workId: string): Promise<Proposals> {
  return proposalsOf(
    await request<ProposalsRead>("PUT", `/v1/library/series/${encodeURIComponent(id)}/work`, { work_id: workId }),
  );
}

/** Le lien de la série défait : l'œuvre trouvée sous son nom revient. */
export async function unlinkWork(id: string): Promise<Proposals> {
  return proposalsOf(await request<ProposalsRead>("DELETE", `/v1/library/series/${encodeURIComponent(id)}/work`));
}

/** Un tome d'une série vu par une adoption : le numéro proposé et le nom qu'il prendrait. */
export type AdoptionFile = {
  readonly itemId: string;
  readonly path: string;
  readonly size: number | null;
  readonly volume: number | null;
  readonly chapter: number | null;
  /** D'où vient le numéro : Jellyfin, le nom du fichier, ou rien. */
  readonly origin: "jellyfin" | "name" | null;
  readonly target: string | null;
  /** Déjà rangé : il ne s'adopte plus. */
  readonly adopted: boolean;
};

export type Adoption = {
  readonly workId: string | null;
  readonly files: readonly AdoptionFile[];
};

export type AdoptionChoice = {
  readonly itemId: string;
  readonly volume: number | null;
  readonly chapter: number | null;
  readonly include: boolean;
};

export type AdoptionResult = {
  readonly adopted: number;
  readonly renamed: boolean;
  readonly conflicts: readonly string[];
};

export async function readAdoption(id: string): Promise<Adoption> {
  const body = await request<{
    readonly work_id: string | null;
    readonly files: readonly {
      readonly item_id: string;
      readonly path: string;
      readonly size: number | null;
      readonly volume: number | null;
      readonly chapter: number | null;
      readonly origin: "jellyfin" | "name" | null;
      readonly target: string | null;
      readonly adopted: boolean;
    }[];
  }>("GET", `/v1/library/series/${encodeURIComponent(id)}/adoption`);
  return {
    workId: body.work_id,
    files: body.files.map((file) => ({
      itemId: file.item_id,
      path: file.path,
      size: file.size,
      volume: file.volume,
      chapter: file.chapter,
      origin: file.origin,
      target: file.target,
      adopted: file.adopted,
    })),
  };
}

/** Les fichiers choisis adoptés ; `place` : renommés d'abord par le rangement. */
export async function adoptFiles(
  id: string,
  choices: readonly AdoptionChoice[],
  place: boolean,
): Promise<AdoptionResult> {
  return request<AdoptionResult>("POST", `/v1/library/series/${encodeURIComponent(id)}/adoption`, {
    items: choices.map((choice) => ({
      item_id: choice.itemId,
      volume: choice.volume,
      chapter: choice.chapter,
      include: choice.include,
    })),
    place,
  });
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

/** Un tome d'une série : un livre ou un livre audio de Jellyfin. */
export type Volume = {
  readonly id: string;
  readonly name: string;
  readonly number: number | null;
  readonly summary: string;
  readonly authors: readonly string[];
  readonly hasImage: boolean;
  readonly fileName: string;
  /** La taille du fichier en octets ; null quand Jellyfin ne la donne pas. */
  readonly size: number | null;
  readonly imageTag: string | null;
};

export type SeriesVolumes = {
  readonly series: Series;
  readonly volumes: readonly Volume[];
  /** Les numéros entre 1 et le plus haut présent qu'aucun tome ne porte. */
  readonly missing: readonly number[];
};

type VolumeRead = {
  readonly id: string;
  readonly name: string;
  readonly number: number | null;
  readonly summary: string;
  readonly authors: readonly string[];
  readonly has_image: boolean;
  readonly file_name: string;
  readonly size: number | null;
  readonly image_tag: string | null;
};

function volumeOf(read: VolumeRead): Volume {
  return {
    id: read.id,
    name: read.name,
    number: read.number,
    summary: read.summary,
    authors: read.authors,
    hasImage: read.has_image,
    fileName: read.file_name,
    size: read.size,
    imageTag: read.image_tag,
  };
}

export async function readVolumes(id: string): Promise<SeriesVolumes> {
  const body = await request<{
    readonly series: SeriesRead;
    readonly volumes: readonly VolumeRead[];
    readonly missing: readonly number[];
  }>("GET", `/v1/library/series/${encodeURIComponent(id)}/volumes`);
  return { series: seriesOf(body.series), volumes: body.volumes.map(volumeOf), missing: body.missing };
}

/** Le fichier d'un tome, lu dans Jellyfin par l'API. */
export function volumeFile(id: string): string {
  return `/api/v1/library/items/${encodeURIComponent(id)}/file`;
}

export type VolumeChange = {
  readonly name: string;
  readonly number: number | null;
  readonly summary: string;
  readonly authors: readonly string[];
  readonly lock: boolean;
  readonly image: ImageChoice | null;
};

export async function changeVolume(id: string, change: VolumeChange): Promise<Volume> {
  const read = await request<VolumeRead>("PUT", `/v1/library/items/${encodeURIComponent(id)}`, {
    name: change.name,
    number: change.number,
    summary: change.summary,
    authors: change.authors,
    lock: change.lock,
    image: imageBody(change.image),
  });
  return volumeOf(read);
}

/** La dernière synchronisation des métadonnées vers Jellyfin. */
export type SyncState = {
  readonly stage: "idle" | "running" | "done" | "failed";
  readonly seriesId: string | null;
  readonly changed: number;
  readonly unchanged: number;
  readonly notFound: number;
};

type SyncRead = {
  readonly stage: SyncState["stage"];
  readonly series_id: string | null;
  readonly changed: number;
  readonly unchanged: number;
  readonly not_found: number;
};

function syncOf(read: SyncRead): SyncState {
  return {
    stage: read.stage,
    seriesId: read.series_id,
    changed: read.changed,
    unchanged: read.unchanged,
    notFound: read.not_found,
  };
}

export async function startSync(seriesId: string | null): Promise<SyncState> {
  return syncOf(await request<SyncRead>("POST", "/v1/library/sync", { series_id: seriesId }));
}

export async function readSync(): Promise<SyncState> {
  return syncOf(await request<SyncRead>("GET", "/v1/library/sync"));
}

/** Une synchronisation lancée, suivie jusqu'à sa fin (relue chaque seconde). */
export async function runSync(seriesId: string | null): Promise<SyncState> {
  let state = await startSync(seriesId);
  while (state.stage === "running") {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    state = await readSync();
  }
  return state;
}
