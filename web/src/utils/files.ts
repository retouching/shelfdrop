import type { Kind } from "../types";

const extensions: Readonly<Record<string, Kind>> = {
  epub: "ebook",
  pdf: "ebook",
  cbz: "manga",
  cbr: "manga",
  m4b: "audiobook",
  mp3: "audiobook",
};

/** Type deviné depuis l'extension d'un fichier ; null quand elle ne dit rien. */
export function guessKind(name: string): Kind | null {
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  return extensions[extension] ?? null;
}
