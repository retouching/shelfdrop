// Maquette : les séries de la bibliothèque Jellyfin (relevées le 21/10), avec l'état de leurs métadonnées.
export type LibraryName = "comics" | "books" | "audiobooks";

export type CoverProposal = {
  readonly id: string;
  /** Une source en ligne, ou un fichier déjà sur le disque. */
  readonly origin: "source" | "local";
  readonly source: string;
  readonly width: number;
  readonly height: number;
  /** Teinte de la vignette de remplacement (la maquette n'affiche pas de vraie image). */
  readonly hue: number;
};

export type Series = {
  readonly id: string;
  readonly library: LibraryName;
  readonly name: string;
  readonly originalTitle: string;
  readonly authors: string;
  readonly year: number | null;
  readonly genres: string;
  readonly volumes: number;
  /** Tomes sans résumé. */
  readonly volumesWithoutSummary: number;
  readonly hasImage: boolean;
  readonly hue: number;
  readonly summary: string;
  /** Résumé proposé par une source, quand la série n'en a pas. */
  readonly proposedSummary: { readonly source: string; readonly text: string } | null;
  readonly covers: readonly CoverProposal[];
};

function covers(id: string, sources: readonly string[], hue: number): readonly CoverProposal[] {
  return sources.map((source, index) => ({
    id: `${id}-${String(index)}`,
    origin: "source",
    source,
    width: index === 0 ? 600 : 400,
    height: index === 0 ? 900 : 600,
    hue: (hue + index * 40) % 360,
  }));
}

/** Les images déjà dans le dossier de la série : couverture de chaque tome (tirée du CBZ, de l'EPUB ou du M4B)
 * et images posées à côté des fichiers. */
function localCovers(
  id: string,
  volumes: number,
  extension: string,
  hue: number,
  extra: readonly string[],
): readonly CoverProposal[] {
  const fromVolumes = Array.from({ length: Math.min(volumes, 4) }, (_, index) => ({
    id: `${id}-local-${String(index)}`,
    origin: "local" as const,
    source: `Tome ${String(index + 1)} · ${extension}`,
    width: 1400,
    height: 2000,
    hue: (hue + 200 + index * 25) % 360,
  }));
  const files = extra.map((name, index) => ({
    id: `${id}-file-${String(index)}`,
    origin: "local" as const,
    source: name,
    width: 1000,
    height: 1500,
    hue: (hue + 120 + index * 30) % 360,
  }));
  return [...files, ...fromVolumes];
}

const extensions = { comics: "CBZ", books: "EPUB", audiobooks: "M4B" } as const;

function series(
  fields: Omit<Series, "covers" | "proposedSummary" | "originalTitle" | "genres"> & {
    readonly originalTitle?: string;
    readonly genres?: string;
    readonly proposedSummary?: Series["proposedSummary"];
    readonly coverSources?: readonly string[];
    readonly folderImages?: readonly string[];
  },
): Series {
  return {
    ...fields,
    originalTitle: fields.originalTitle ?? "",
    genres: fields.genres ?? "",
    proposedSummary: fields.proposedSummary ?? null,
    covers: [
      ...localCovers(fields.id, fields.volumes, extensions[fields.library], fields.hue, fields.folderImages ?? []),
      ...covers(
        fields.id,
        fields.coverSources ?? ["MangaUpdates", "Kitsu", "MyAnimeList", "AniList", "MangaDex"],
        fields.hue,
      ),
    ],
  };
}

export const mockSeries: readonly Series[] = [
  series({
    id: "s1",
    library: "comics",
    name: "Berserk",
    originalTitle: "ベルセルク",
    authors: "Kentaro Miura",
    year: 1990,
    genres: "Dark fantasy, Seinen",
    volumes: 43,
    volumesWithoutSummary: 43,
    hasImage: true,
    hue: 8,
    summary: "",
    proposedSummary: {
      source: "MangaUpdates",
      text: "Guts, un mercenaire marqué par une malédiction, traque les apôtres qui ont massacré ses compagnons.",
    },
  }),
  series({
    id: "s2",
    library: "comics",
    name: "Chainsaw Man",
    originalTitle: "チェンソーマン",
    authors: "Tatsuki Fujimoto",
    year: 2018,
    genres: "Action, Shōnen",
    volumes: 22,
    volumesWithoutSummary: 17,
    hasImage: true,
    hue: 20,
    summary: "Denji, criblé de dettes, fusionne avec son démon-tronçonneuse Pochita.",
  }),
  series({
    id: "s3",
    library: "comics",
    name: "Dusk Maiden of Amnesia",
    originalTitle: "黄昏乙女×アムネジア",
    authors: "Maybe",
    year: 2009,
    genres: "Mystère, Romance",
    volumes: 10,
    volumesWithoutSummary: 10,
    hasImage: false,
    hue: 280,
    folderImages: ["folder.jpg"],
    summary: "",
    proposedSummary: {
      source: "Kitsu",
      text: "Teiichi découvre dans l'aile désaffectée de son lycée le fantôme d'une élève sans mémoire, Yūko.",
    },
  }),
  series({
    id: "s4",
    library: "comics",
    name: "Horimiya",
    originalTitle: "ホリミヤ",
    authors: "HERO, Daisuke Hagiwara",
    year: 2011,
    genres: "Romance, Tranche de vie",
    volumes: 16,
    volumesWithoutSummary: 16,
    hasImage: true,
    hue: 330,
    summary: "",
    proposedSummary: {
      source: "MangaUpdates",
      text: "Hori, élève modèle, et Miyamura, garçon effacé, découvrent chacun le vrai visage de l'autre.",
    },
  }),
  series({
    id: "s5",
    library: "comics",
    name: "Gunnm",
    originalTitle: "銃夢",
    authors: "Yukito Kishiro",
    year: 1990,
    genres: "Cyberpunk, Seinen",
    volumes: 9,
    volumesWithoutSummary: 9,
    hasImage: false,
    hue: 200,
    summary: "",
    proposedSummary: {
      source: "MangaUpdates",
      text: "Dans une décharge au pied de la cité céleste de Zalem, Ido trouve la tête d'une cyborg, Gally.",
    },
  }),
  series({
    id: "s6",
    library: "comics",
    name: "Kaguya-sama - Love is War",
    originalTitle: "かぐや様は告らせたい",
    authors: "Aka Akasaka",
    year: 2015,
    genres: "Comédie, Romance",
    volumes: 28,
    volumesWithoutSummary: 0,
    hasImage: true,
    hue: 0,
    summary: "Kaguya et Miyuki, à la tête du conseil des élèves, s'aiment et refusent d'être le premier à l'avouer.",
  }),
  series({
    id: "s7",
    library: "comics",
    name: "Ichi the Witch",
    originalTitle: "魔男のイチ",
    authors: "Osamu Nishi, Shiro Usazaki",
    year: 2024,
    genres: "Fantasy, Shōnen",
    volumes: 2,
    volumesWithoutSummary: 0,
    hasImage: true,
    hue: 140,
    summary: "Ichi, chasseur dans la montagne, devient le premier homme à maîtriser la magie.",
  }),
  series({
    id: "s8",
    library: "books",
    name: "Plus rien ne pourra me blesser",
    originalTitle: "Can't Hurt Me",
    authors: "David Goggins",
    year: 2018,
    genres: "Développement personnel",
    volumes: 1,
    volumesWithoutSummary: 1,
    hasImage: true,
    hue: 30,
    summary: "",
    proposedSummary: {
      source: "Open Library",
      text: "Des quartiers pauvres de l'Indiana aux Navy SEALs, le parcours de David Goggins.",
    },
    coverSources: ["Open Library"],
  }),
  series({
    id: "s9",
    library: "books",
    name: "La Tresse",
    authors: "Laetitia Colombani",
    year: 2017,
    genres: "Roman",
    volumes: 1,
    volumesWithoutSummary: 0,
    hasImage: true,
    hue: 50,
    summary: "Trois femmes, trois continents, trois destins liés par une tresse.",
    coverSources: ["Open Library"],
  }),
  series({
    id: "s10",
    library: "audiobooks",
    name: "La Mémoire des os",
    authors: "Margot Looten",
    year: 2025,
    genres: "Fantasy",
    volumes: 2,
    volumesWithoutSummary: 2,
    hasImage: true,
    hue: 260,
    summary: "",
    proposedSummary: {
      source: "Open Library",
      text: "Dans un monde où les os gardent la mémoire des morts, une jeune nécromancienne remonte un complot.",
    },
    coverSources: ["Open Library"],
  }),
  series({
    id: "s11",
    library: "audiobooks",
    name: "Ne cède jamais",
    originalTitle: "Never Finished",
    authors: "David Goggins",
    year: 2023,
    genres: "Développement personnel",
    volumes: 1,
    volumesWithoutSummary: 1,
    hasImage: true,
    hue: 20,
    summary: "",
    proposedSummary: {
      source: "Wikidata",
      text: "La suite de Plus rien ne pourra me blesser : la discipline mentale face à l'échec.",
    },
    coverSources: ["Open Library"],
  }),
  series({
    id: "s12",
    library: "audiobooks",
    name: "Les Aventuriers de la mer",
    authors: "Robin Hobb",
    year: 1998,
    genres: "Fantasy",
    volumes: 9,
    volumesWithoutSummary: 0,
    hasImage: true,
    hue: 190,
    summary: "Les vivenefs de Terrilville, navires de bois-sorcier qui prennent vie.",
    coverSources: ["Open Library"],
  }),
];
