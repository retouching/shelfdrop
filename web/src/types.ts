export type Kind = "manga" | "ebook" | "audiobook";

/** Tomes couverts par une release : un seul, une plage (pack), ou une intégrale sans numéros. */
export type Volumes =
  | { readonly kind: "single"; readonly number: number }
  | { readonly kind: "range"; readonly from: number; readonly to: number }
  | { readonly kind: "complete" }
  | { readonly kind: "unknown" };

export type MetadataSource = "AniList" | "Open Library" | "Wikidata" | "Hardcover";

export type AltTitle = {
  readonly title: string;
  readonly language: string;
};

/** Une œuvre trouvée dans les API de métadonnées, avec tous ses noms connus. */
export type Work = {
  readonly id: string;
  readonly source: MetadataSource;
  readonly title: string;
  readonly author: string;
  readonly year: number;
  readonly volumeCount: number | null;
  readonly titles: readonly AltTitle[];
};

export type Release = {
  readonly id: string;
  readonly title: string;
  readonly matchedName: string;
  readonly infoUrl: string;
  readonly indexer: string;
  readonly indexerRank: number;
  readonly seeders: number;
  readonly sizeBytes: number;
  readonly author: string;
  readonly series: string;
  readonly volumes: Volumes;
};

export type DownloadState =
  | { readonly kind: "downloading"; readonly percent: number }
  | { readonly kind: "waiting" }
  | { readonly kind: "placing" }
  | { readonly kind: "placed"; readonly library: string }
  | { readonly kind: "toPlace" }
  | { readonly kind: "failed"; readonly reason: "not_received" | "duplicate" };

export type Download = {
  readonly id: string;
  readonly label: string;
  readonly kind: Kind;
  readonly state: DownloadState;
  readonly addedAt: string;
};

/** Un fichier à ranger : envoyé depuis la page, ou trouvé dans la bibliothèque ou les téléchargements. */
export type FileOrigin = "upload" | "library" | "download";

export type FileState =
  | { readonly kind: "uploading"; readonly percent: number }
  | { readonly kind: "unlinked" }
  | { readonly kind: "misplaced"; readonly reason: string }
  | { readonly kind: "placing"; readonly destination: string }
  | { readonly kind: "placed"; readonly destination: string };

export type ShelfFile = {
  readonly id: string;
  readonly name: string;
  readonly path: string;
  readonly origin: FileOrigin;
  readonly kind: Kind | null;
  readonly sizeBytes: number;
  readonly state: FileState;
};
