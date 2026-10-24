// Les fichiers de Ranger : lus dans l'API, relus toutes les 5 s sur la page Ranger, chaque minute ailleurs (compteur du menu).
import { useCallback, useEffect, useState } from "react";

import type { FileOrigin, Kind, ShelfFile } from "../types";
import { request } from "./http";

type ItemRead = {
  readonly id: string;
  readonly origin: FileOrigin;
  readonly kind: Kind | null;
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly state: "unlinked" | "chapters" | "misplaced" | "placed" | "ignored" | "placing";
  readonly reason: string | null;
  readonly error: string | null;
  readonly destination: string | null;
  readonly chapters: readonly number[];
  readonly existing: readonly number[];
  readonly loose: readonly number[];
  readonly series: string;
  readonly author: string;
  readonly work_id: string | null;
};

type ItemsRead = { readonly items: readonly ItemRead[]; readonly open: number };

/** Ce que la page demande au rangement pour un fichier. */
export type PlaceBody =
  | {
      readonly type: "volume";
      readonly kind: Kind;
      readonly work_id: string | null;
      readonly series: string;
      readonly author: string;
      readonly volume: number | null;
      readonly title: string;
    }
  | {
      readonly type: "chapter";
      readonly work_id: string | null;
      readonly series: string;
      readonly author: string;
      readonly first: number;
      readonly last: number | null;
      readonly volume: number | null;
    }
  | {
      readonly type: "chapters";
      readonly work_id: string | null;
      readonly series: string;
      readonly author: string;
      readonly summary: string;
      readonly volumes: readonly {
        readonly volume: number;
        readonly first: number;
        readonly last: number;
        readonly replace: boolean;
      }[];
      readonly rest: "place" | "keep";
    }
  | { readonly type: "ignore" };

function fileOf(read: ItemRead): ShelfFile {
  const state: ShelfFile["state"] =
    read.state === "placing"
      ? { kind: "placing", destination: read.destination ?? "" }
      : read.state === "placed"
        ? { kind: "placed", destination: read.destination ?? "" }
        : read.state === "misplaced"
          ? { kind: "misplaced", reason: read.reason ?? "" }
          : { kind: read.state };
  return {
    id: read.id,
    name: read.name,
    path: read.path,
    origin: read.origin,
    kind: read.kind,
    sizeBytes: read.size,
    state,
    error: read.error,
    series: read.series,
    author: read.author,
    workId: read.work_id,
    ...(read.state === "chapters" || read.chapters.length > 0
      ? { chapters: { numbers: read.chapters, existing: read.existing, loose: read.loose } }
      : {}),
  };
}

export type PlaceList = { readonly files: readonly ShelfFile[]; readonly open: number };

export async function readPlace(text: string): Promise<PlaceList> {
  const params = new URLSearchParams({ q: text });
  const read = await request<ItemsRead>("GET", `/v1/place/items?${params.toString()}`);
  return { files: read.items.map(fileOf), open: read.open };
}

/** Le rangement d'un fichier, confié au serveur ; un fichier déjà rangé passe par sa correction. */
export async function placeFile(id: string, body: PlaceBody): Promise<ShelfFile> {
  const [prefix, number] = id.split("-");
  const path = prefix === "shelf" ? `/v1/place/shelf/${number ?? ""}/link` : `/v1/place/items/${number ?? ""}/link`;
  return fileOf(await request<ItemRead>("POST", path, body));
}

/** Un fichier ignoré remis parmi les fichiers à ranger. */
export async function resumeFile(id: string): Promise<ShelfFile> {
  const number = id.split("-")[1] ?? "";
  return fileOf(await request<ItemRead>("POST", `/v1/place/items/${number}/resume`));
}

export async function askScan(): Promise<void> {
  await request<null>("POST", "/v1/place/scan");
}

const PAGE_EVERY_MS = 5000;
const MENU_EVERY_MS = 60_000;

export type PlaceState = PlaceList & { readonly loaded: boolean; readonly refresh: () => void };

/** La liste de Ranger et son compteur ; `text` cherche aussi dans les fichiers déjà rangés. */
export function usePlace(enabled: boolean, onPage: boolean, text: string): PlaceState {
  const [list, setList] = useState<PlaceList & { readonly loaded: boolean }>({ files: [], open: 0, loaded: false });
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    let cancelled = false;
    function load(): void {
      readPlace(text).then(
        (read) => {
          if (!cancelled) {
            setList({ ...read, loaded: true });
          }
        },
        () => undefined,
      );
    }
    load();
    const timer = window.setInterval(load, onPage ? PAGE_EVERY_MS : MENU_EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [enabled, onPage, text, round]);

  const refresh = useCallback(() => {
    setRound((n) => n + 1);
  }, []);
  return { ...list, refresh };
}
