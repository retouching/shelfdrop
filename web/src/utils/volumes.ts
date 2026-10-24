// Règles pures sur les tomes : libellés, couverture d'une sélection, meilleure release par tome.
import { locale, texts } from "../texts";
import type { Release, Volumes } from "../types";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function volumesLabel(volumes: Volumes): string {
  switch (volumes.kind) {
    case "single":
      return texts.volumeLabels.volume(pad(volumes.number));
    case "range":
      return texts.volumeLabels.range(pad(volumes.from), pad(volumes.to));
    case "complete":
      return texts.volumeLabels.complete;
    case "unknown":
      return "?";
  }
}

export function volumeNumbers(volumes: Volumes): readonly number[] {
  switch (volumes.kind) {
    case "single":
      return [volumes.number];
    case "range":
      return Array.from({ length: volumes.to - volumes.from + 1 }, (_, i) => volumes.from + i);
    case "complete":
    case "unknown":
      return [];
  }
}

/** Score des filtres, puis l'ordre des trackers choisi dans Paramètres, puis les seeds. */
export function compareReleases(a: Release, b: Release): number {
  return b.score - a.score || a.indexerRank - b.indexerRank || b.seeders - a.seeders;
}

/**
 * Une release par tome, la mieux classée, sans doublon avec un pack déjà coché : les packs de
 * `selected` restent, les tomes qu'ils couvrent ne reçoivent rien de plus.
 */
export function bestPerVolume(
  releases: readonly Release[],
  selected: ReadonlySet<string> = new Set(),
): readonly string[] {
  const packs = releases.filter((release) => selected.has(release.id) && release.volumes.kind !== "single");
  const covered = new Set(packs.flatMap((release) => volumeNumbers(release.volumes)));
  const best = new Map<number, Release>();
  for (const release of releases) {
    if (release.volumes.kind !== "single" || covered.has(release.volumes.number)) {
      continue;
    }
    const current = best.get(release.volumes.number);
    if (current === undefined || compareReleases(release, current) < 0) {
      best.set(release.volumes.number, release);
    }
  }
  return [...packs, ...best.values()].map((release) => release.id);
}

/** « T01 à T22 », « T01, T03 et T05 à T07 » : les tomes couverts par une sélection. */
export function coverageLabel(releases: readonly Release[]): string {
  if (releases.some((release) => release.volumes.kind === "complete")) {
    return texts.volumeLabels.complete;
  }
  const numbers = [...new Set(releases.flatMap((release) => volumeNumbers(release.volumes)))].sort((a, b) => a - b);
  if (numbers.length === 0) {
    return texts.volumeLabels.unknown;
  }
  const parts: string[] = [];
  let start = numbers[0] ?? 0;
  let previous = start;
  for (const n of [...numbers.slice(1), Number.NaN]) {
    if (n === previous + 1) {
      previous = n;
      continue;
    }
    parts.push(
      start === previous ? texts.volumeLabels.volume(pad(start)) : texts.volumeLabels.range(pad(start), pad(previous)),
    );
    start = n;
    previous = n;
  }
  return new Intl.ListFormat(locale, { type: "conjunction" }).format(parts);
}

/** Valeur du champ « Tomes » : « 6 », « 1-41 », vide pour une intégrale ou un livre seul. */
export function volumesInput(volumes: Volumes): string {
  switch (volumes.kind) {
    case "single":
      return String(volumes.number);
    case "range":
      return `${String(volumes.from)}-${String(volumes.to)}`;
    case "complete":
    case "unknown":
      return "";
  }
}

export function parseVolumesInput(value: string): Volumes {
  const text = value.trim();
  if (text === "") {
    return { kind: "complete" };
  }
  const range = /^(\d{1,3})\s*[-–à]\s*(\d{1,3})$/u.exec(text);
  if (range !== null) {
    const from = Number(range[1]);
    const to = Number(range[2]);
    return from <= to ? { kind: "range", from, to } : { kind: "unknown" };
  }
  return /^\d{1,3}$/u.test(text) ? { kind: "single", number: Number(text) } : { kind: "unknown" };
}

function firstVolume(volumes: Volumes): number {
  switch (volumes.kind) {
    case "single":
      return volumes.number;
    case "range":
      return volumes.from;
    case "complete":
    case "unknown":
      return 0;
  }
}

/** Affichage : packs et intégrales d'abord, puis tome par tome ; à tome égal, l'ordre des trackers puis les seeds. */
export function compareForDisplay(a: Release, b: Release): number {
  const packA = a.volumes.kind === "single" ? 1 : 0;
  const packB = b.volumes.kind === "single" ? 1 : 0;
  return packA - packB || firstVolume(a.volumes) - firstVolume(b.volumes) || compareReleases(a, b);
}
