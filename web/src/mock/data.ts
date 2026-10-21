// Données fictives de la maquette, reprises de vraies releases vues sur les trackers.
import type { Kind, Release, Work } from "../types";

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
  fields: Omit<
    Release,
    "indexerRank" | "indexer" | "infoUrl" | "matchedName" | "score" | "scoreRules" | "automatic"
  > & {
    readonly indexer: Indexer;
    readonly matchedName?: string;
  },
): Release {
  return {
    ...fields,
    matchedName: fields.matchedName ?? fields.series,
    infoUrl: `${trackerPages[fields.indexer]}${fields.id}`,
    indexerRank: rank[fields.indexer],
    score: 0,
    scoreRules: [],
    automatic: fields.indexer !== "C411",
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
        { title: "Never Finished: Unshackle Your Mind and Win the War Within", language: "EN" },
      ],
    },
    {
      id: "wikidata-Q115870318",
      source: "Wikidata",
      title: "Never Finished: Unshackle Your Mind and Win the War Within",
      author: "David Goggins",
      year: 2022,
      volumeCount: null,
      titles: [
        { title: "Never Finished: Unshackle Your Mind and Win the War Within", language: "EN" },
        { title: "Nunca terminado", language: "ES" },
      ],
    },
    {
      id: "bnf-cb47168934r",
      source: "BnF",
      title: "Ne cède jamais",
      author: "David Goggins",
      year: 2023,
      volumeCount: null,
      titles: [
        { title: "Ne cède jamais", language: "FR" },
        { title: "Ne cède jamais : libère ton mental et gagne la guerre intérieure", language: "FR" },
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
    id: "csm-eng",
    title: "Chainsaw Man v01-v11 (2020-2023) (Digital) (1r0n)",
    indexer: "Nyaa.si",
    seeders: 212,
    sizeBytes: 2_900 * mb,
    author: "Tatsuki Fujimoto",
    series: "Chainsaw Man",
    volumes: { kind: "range", from: 1, to: 11 },
  }),
  release({
    id: "csm-raw",
    title: "[RAW] チェンソーマン 第01-17巻 (JPN)",
    indexer: "Nyaa.si",
    seeders: 38,
    sizeBytes: 3_400 * mb,
    author: "Tatsuki Fujimoto",
    series: "Chainsaw Man",
    matchedName: "チェンソーマン",
    volumes: { kind: "range", from: 1, to: 17 },
  }),
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

/** Never Finished : une release sous le nom anglais, une sous le nom français. */
const neverFinished: Readonly<Record<string, readonly Release[]>> = {
  "openlibrary-OL27896384W": [
    release({
      id: "e21",
      title: "David Goggins - Never Finished (2022) EPUB",
      indexer: "The Old School",
      seeders: 41,
      sizeBytes: 2.1 * mb,
      author: "David Goggins",
      series: "Never Finished",
      volumes: { kind: "complete" },
    }),
  ],
  "bnf-cb47168934r": [
    release({
      id: "e22",
      title: "David.Goggins.Ne.Cede.Jamais.2023.French.Epub-NoTag",
      indexer: "Abnormal",
      seeders: 17,
      sizeBytes: 2.6 * mb,
      author: "David Goggins",
      series: "Ne cède jamais",
      volumes: { kind: "complete" },
    }),
  ],
};

/** Releases trouvées pour une œuvre (la 1re œuvre de chaque type en a ; les autres montrent l'état vide).
 * Une œuvre fusionnée a les releases de ses deux parties. */
export function mockReleasesForWork(kind: Kind, workId: string): readonly Release[] {
  const parts = workId.split("+");
  return parts.flatMap((part) => (mockWorks[kind][0]?.id === part ? mockResults[kind] : (neverFinished[part] ?? [])));
}
