// Règles pures sur les tomes : libellés, couverture d'une sélection, meilleure release par tome.
import type { Release, Volumes } from "../types";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function volumesLabel(volumes: Volumes): string {
  switch (volumes.kind) {
    case "single":
      return `T${pad(volumes.number)}`;
    case "range":
      return `T${pad(volumes.from)} à T${pad(volumes.to)}`;
    case "complete":
      return "Intégrale";
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

/** Une release par tome, la mieux classée, en laissant de côté les packs. */
export function bestPerVolume(releases: readonly Release[]): readonly string[] {
  const best = new Map<number, Release>();
  for (const release of releases) {
    if (release.volumes.kind !== "single") {
      continue;
    }
    const current = best.get(release.volumes.number);
    if (current === undefined || compareReleases(release, current) < 0) {
      best.set(release.volumes.number, release);
    }
  }
  return [...best.values()].map((release) => release.id);
}

/** « T01 à T22 », « T01, T03 et T05 à T07 » : les tomes couverts par une sélection. */
export function coverageLabel(releases: readonly Release[]): string {
  if (releases.some((release) => release.volumes.kind === "complete")) {
    return "Intégrale";
  }
  const numbers = [...new Set(releases.flatMap((release) => volumeNumbers(release.volumes)))].sort((a, b) => a - b);
  if (numbers.length === 0) {
    return "Tome inconnu";
  }
  const parts: string[] = [];
  let start = numbers[0] ?? 0;
  let previous = start;
  for (const n of [...numbers.slice(1), Number.NaN]) {
    if (n === previous + 1) {
      previous = n;
      continue;
    }
    parts.push(start === previous ? `T${pad(start)}` : `T${pad(start)} à T${pad(previous)}`);
    start = n;
    previous = n;
  }
  if (parts.length === 1) {
    return parts[0] ?? "";
  }
  return `${parts.slice(0, -1).join(", ")} et ${parts.at(-1) ?? ""}`;
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
