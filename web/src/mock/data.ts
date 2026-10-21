// Données fictives de la maquette, reprises de vraies releases vues sur les trackers.
import type { Download, Kind, Release, Work } from "../types";

const mb = 1_000_000;
const rank = { "Nyaa.si": 0, "The Old School": 1, Abnormal: 2, C411: 3 } as const;
type Indexer = keyof typeof rank;

const trackerPages: Readonly<Record<Indexer, string>> = {
  "Nyaa.si": "https://nyaa.si/view/",
  "The Old School": "https://theoldschool.cc/torrents/",
  Abnormal: "https://abn.lol/Torrent/Details?ReleaseId=",
  C411: "https://c411.org/torrents/",
};

function release(
  fields: Omit<Release, "indexerRank" | "indexer" | "infoUrl" | "matchedName"> & {
    readonly indexer: Indexer;
    readonly matchedName?: string;
  },
): Release {
  return {
    ...fields,
    matchedName: fields.matchedName ?? fields.series,
    infoUrl: `${trackerPages[fields.indexer]}${fields.id}`,
    indexerRank: rank[fields.indexer],
  };
}

export const mockWorks: Readonly<Record<Kind, readonly Work[]>> = {
  manga: [
    {
      id: "anilist-105778",
      source: "AniList",
      title: "Chainsaw Man",
      author: "Tatsuki Fujimoto",
      year: 2018,
      volumeCount: 22,
      titles: [
        { title: "Chainsaw Man", language: "EN" },
        { title: "Chensō Man", language: "Romaji" },
        { title: "チェンソーマン", language: "JA" },
        { title: "Chainsaw.Man", language: "Release" },
      ],
    },
    {
      id: "anilist-151807",
      source: "AniList",
      title: "Chainsaw Man: Buddy Stories",
      author: "Tatsuki Fujimoto, Sakaku Hishikawa",
      year: 2021,
      volumeCount: 1,
      titles: [
        { title: "Chainsaw Man: Buddy Stories", language: "EN" },
        { title: "Chensō Man Badi Sutōrīzu", language: "Romaji" },
      ],
    },
  ],
  ebook: [
    {
      id: "wikidata-Q56025787",
      source: "Wikidata",
      title: "Can't Hurt Me",
      author: "David Goggins",
      year: 2018,
      volumeCount: null,
      titles: [
        { title: "Can't Hurt Me", language: "EN" },
        { title: "Plus rien ne pourra me blesser", language: "FR" },
        { title: "Nada me puede lastimar", language: "ES" },
      ],
    },
    {
      id: "openlibrary-OL27896384W",
      source: "Open Library",
      title: "Never Finished",
      author: "David Goggins",
      year: 2022,
      volumeCount: null,
      titles: [
        { title: "Never Finished", language: "EN" },
        { title: "Ne cède jamais", language: "FR" },
      ],
    },
  ],
  audiobook: [
    {
      id: "openlibrary-OL41022713W",
      source: "Open Library",
      title: "La Mémoire des os",
      author: "Margot Looten",
      year: 2025,
      volumeCount: 2,
      titles: [
        { title: "La Mémoire des os", language: "FR" },
        { title: "Le Dragon et l'Oiseau", language: "FR, tome 1" },
        { title: "La Phalène et l'Araignée", language: "FR, tome 2" },
      ],
    },
  ],
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

const chainsawSingles: readonly Release[] = Array.from({ length: 22 }, (_, i) => {
  const n = i + 1;
  const onTos = ![16, 20, 22].includes(n);
  return release({
    id: `csm-${pad(n)}`,
    title: onTos
      ? `Chainsaw.Man.T${pad(n)}.FRENCH.CBZ.eBook-Paprika+.cbz`
      : `Chainsaw.Man.T${pad(n)}.Tatsuki.FUJIMOTO.FRENCH.[CBZ]-ebdz`,
    indexer: onTos ? "The Old School" : "C411",
    seeders: onTos ? 4 + (n % 5) : 51 + (n % 3),
    sizeBytes: (230 + n * 7) * mb,
    author: "Tatsuki Fujimoto",
    series: "Chainsaw Man",
    volumes: { kind: "single", number: n },
  });
});

const chainsawC411Doubles: readonly Release[] = [1, 2, 3].map((n) =>
  release({
    id: `csm-c411-${pad(n)}`,
    title: `Chainsaw.Man.T${pad(n)}.Tatsuki.FUJIMOTO.FRENCH.[CBZ]-ebdz`,
    indexer: "C411",
    seeders: 53,
    sizeBytes: 71 * mb,
    author: "Tatsuki Fujimoto",
    series: "Chainsaw Man",
    volumes: { kind: "single", number: n },
  }),
);

const chainsawPacks: readonly Release[] = [
  release({
    id: "csm-color",
    title: "Chainsaw.Man.FullColor.FR.T01-T11.CBZ-Chromatique",
    indexer: "The Old School",
    seeders: 4,
    sizeBytes: 10_300 * mb,
    author: "Tatsuki Fujimoto",
    series: "Chainsaw Man (couleur)",
    matchedName: "Chainsaw Man",
    volumes: { kind: "range", from: 1, to: 11 },
  }),
];

export const mockQueries: Readonly<Record<Kind, string>> = {
  manga: "Chainsaw Man",
  ebook: "Can't Hurt Me",
  audiobook: "Mémoire des os",
};

export const mockResults: Readonly<Record<Kind, readonly Release[]>> = {
  manga: [...chainsawPacks, ...chainsawSingles, ...chainsawC411Doubles],
  ebook: [
    release({
      id: "e1",
      title: "David.Goggins.2023.Plus.Rien.Ne.Pourra.Me.Blesser.French.Epub-NoGRP",
      indexer: "Abnormal",
      seeders: 2,
      sizeBytes: 1 * mb,
      author: "David Goggins",
      series: "Plus rien ne pourra me blesser",
      matchedName: "Plus rien ne pourra me blesser",
      volumes: { kind: "unknown" },
    }),
  ],
  audiobook: [
    release({
      id: "a1",
      title: "La.Mémoire.Des.Os.T01.Le.Dragon.Et.Loiseau.Margot.Looten.2025.FR.[MP3.128kbps]-NOTAG",
      indexer: "C411",
      seeders: 28,
      sizeBytes: 1463 * mb,
      author: "Margot Looten",
      series: "La Mémoire des os",
      volumes: { kind: "single", number: 1 },
    }),
    release({
      id: "a2",
      title: "La.Memoire.Des.Os.T02.La.Phalene.Et.L.Araignee.Margot.Looten.2026.FR.[Mp3.128.Kbps]-NOTAG",
      indexer: "C411",
      seeders: 32,
      sizeBytes: 1623 * mb,
      author: "Margot Looten",
      series: "La Mémoire des os",
      volumes: { kind: "single", number: 2 },
    }),
  ],
};

export const mockDownloads: readonly Download[] = [
  {
    id: "d1",
    label: "Berserk - T01 à T41",
    kind: "manga",
    state: { kind: "downloading", percent: 77 },
    addedAt: "15:02",
  },
  {
    id: "d2",
    label: "La Mémoire des os - T02 - La phalène et l'araignée",
    kind: "audiobook",
    state: { kind: "placing" },
    addedAt: "14:48",
  },
  {
    id: "d3",
    label: "Dusk Maiden of Amnesia - Intégrale",
    kind: "manga",
    state: { kind: "placed", library: "BD & Mangas" },
    addedAt: "14:31",
  },
  {
    id: "d4",
    label: "Ichi the Witch - T03",
    kind: "manga",
    state: { kind: "failed", reason: "not_received" },
    addedAt: "14:12",
  },
];

/** Releases trouvées pour une œuvre (la 1re œuvre de chaque type en a ; les autres montrent l'état vide). */
export function mockReleasesForWork(kind: Kind, workId: string): readonly Release[] {
  return mockWorks[kind][0]?.id === workId ? mockResults[kind] : [];
}
