// Maquette : fichiers à ranger (bibliothèque et téléchargements). Données fictives.
import type { ShelfFile } from "../types";

const chainsawChapters: readonly number[] = [
  ...Array.from({ length: 232 }, (_, i) => i + 1).filter((n) => n !== 98 && (n < 212 || n > 214)),
  10.5,
  54.5,
].sort((a, b) => a - b);

export const mockFiles: readonly ShelfFile[] = [
  {
    id: "f0",
    name: "Chainsaw Man - Ch. 001-232 [Scan FR]",
    path: "téléchargements/manga/Chainsaw Man - Ch. 001-232 [Scan FR]/",
    origin: "download",
    kind: "manga",
    sizeBytes: 4_100_000_000,
    state: { kind: "chapters" },
    chapters: { numbers: chainsawChapters, existing: Array.from({ length: 22 }, (_, i) => i + 1) },
  },
  {
    id: "f1",
    name: "David.Goggins.2023.Plus.Rien.Ne.Pourra.Me.Blesser.French.epub",
    path: "Livres/David.Goggins.2023.Plus.Rien.Ne.Pourra.Me.Blesser.French.epub",
    origin: "library",
    kind: "ebook",
    sizeBytes: 3_400_000,
    state: { kind: "misplaced", reason: "à la racine de Livres" },
  },
  {
    id: "f9",
    name: "Chainsaw Man Ch. 233-236 [Scan FR].cbz",
    path: "téléchargements/manga/Chainsaw Man Ch. 233-236 [Scan FR].cbz",
    origin: "download",
    kind: "manga",
    sizeBytes: 21_000_000,
    state: { kind: "unlinked" },
  },
  {
    id: "f2",
    name: "Chainsaw Man T23.cbz",
    path: "téléchargements/manga/Chainsaw Man T23.cbz",
    origin: "download",
    kind: "manga",
    sizeBytes: 98_000_000,
    state: { kind: "unlinked" },
  },
  {
    id: "f3",
    name: "Never Finished - chap 01-12.zip",
    path: "téléchargements/audiobook/Never Finished - chap 01-12.zip",
    origin: "download",
    kind: "audiobook",
    sizeBytes: 412_000_000,
    state: { kind: "unlinked" },
  },
  {
    id: "f4",
    name: "Chainsaw Man - T22.cbz",
    path: "BD & Mangas/Chainsaw Man/Chainsaw Man - T22.cbz",
    origin: "library",
    kind: "manga",
    sizeBytes: 101_000_000,
    state: { kind: "placed", destination: "BD & Mangas › Chainsaw Man" },
  },
  {
    id: "f5",
    name: "La Mémoire des os - T01 - Le dragon et l'oiseau.m4b",
    path: "Livres audio/Margot Looten/La Mémoire des os/01 - Le dragon et l'oiseau/",
    origin: "library",
    kind: "audiobook",
    sizeBytes: 1_150_000_000,
    state: { kind: "placed", destination: "Livres audio › Margot Looten › La Mémoire des os" },
  },
];

const extensions: Readonly<Record<string, ShelfFile["kind"]>> = {
  epub: "ebook",
  pdf: "ebook",
  cbz: "manga",
  cbr: "manga",
  m4b: "audiobook",
  mp3: "audiobook",
};

/** Type deviné depuis l'extension ; le serveur regardera aussi le contenu. */
export function guessKind(name: string): ShelfFile["kind"] {
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  return extensions[extension] ?? null;
}
