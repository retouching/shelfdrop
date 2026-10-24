// Envoi de fichiers de la page Manuel : POST /api/v1/uploads, les morceaux de 50 Mio en PUT, puis
// l'empreinte SHA-256 du fichier entier ; un envoi coupé reprend où il en était.
import { Sha256 } from "../utils/sha256";
import { ApiError, request } from "./http";

type UploadRead = {
  readonly id: number;
  readonly name: string;
  readonly size: number;
  readonly chunk_size: number;
  readonly chunks: number;
  readonly received: readonly number[];
  readonly state: "receiving" | "verified" | "listed" | "corrupt" | "lost";
};

/** Pourquoi un envoi n'a pas abouti. */
export type UploadFailure = "interrupted" | "corrupt" | "type" | "size";

export class UploadError extends Error {
  readonly reason: UploadFailure;

  constructor(reason: UploadFailure) {
    super(reason);
    this.name = "UploadError";
    this.reason = reason;
  }
}

/** 5 Gio au plus par fichier, comme le serveur. */
const MAX_BYTES = 5 * 1024 ** 3;
/** Essais d'un morceau, et l'attente avant chacun des suivants. */
const RETRY_WAITS_MS = [2000, 5000, 10000];

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/** Un morceau envoyé : le statut de la réponse, 0 si la connexion a coupé. `onSent` reçoit les
 * octets du morceau déjà partis (XMLHttpRequest : fetch ne dit pas où en est un envoi). */
function putChunk(url: string, data: ArrayBuffer, onSent: (bytes: number) => void): Promise<number> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (event) => {
      onSent(event.loaded);
    };
    xhr.onload = () => {
      resolve(xhr.status);
    };
    xhr.onerror = () => {
      resolve(0);
    };
    xhr.onabort = () => {
      resolve(0);
    };
    xhr.send(data);
  });
}

async function sendChunk(id: number, index: number, data: ArrayBuffer, onSent: (bytes: number) => void): Promise<void> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      const status = await putChunk(`/api/v1/uploads/${String(id)}/chunks/${String(index)}`, data, onSent);
      if (status >= 200 && status < 300) {
        return;
      }
      if (status !== 0 && status < 500 && status !== 429) {
        throw new UploadError("interrupted");
      }
    } catch (error) {
      if (error instanceof UploadError) {
        throw error;
      }
    }
    const pause = RETRY_WAITS_MS[attempt];
    if (pause === undefined) {
      throw new UploadError("interrupted");
    }
    await wait(pause);
  }
}

function failureOf(error: unknown): UploadError {
  if (error instanceof UploadError) {
    return error;
  }
  if (error instanceof ApiError && error.code === "upload_corrupt") {
    return new UploadError("corrupt");
  }
  if (error instanceof ApiError && error.code === "upload_refused") {
    return new UploadError("type");
  }
  return new UploadError("interrupted");
}

/** Où en est un envoi : les octets partis (ou déjà reçus d'un envoi repris), et la vérification
 * du fichier entier par le serveur une fois tout parti. */
export type UploadProgress = { readonly sent: number; readonly total: number; readonly checking: boolean };

/** Le fichier envoyé par morceaux (ceux déjà reçus sont sautés), puis vérifié par le serveur.
 * `onProgress` suit les octets partis. Lève UploadError. */
export async function uploadFile(file: File, onProgress: (progress: UploadProgress) => void): Promise<void> {
  if (file.size === 0 || file.size > MAX_BYTES) {
    throw new UploadError("size");
  }
  try {
    const upload = await request<UploadRead>("POST", "/v1/uploads", { name: file.name, size: file.size });
    const received = new Set(upload.received);
    const hash = new Sha256();
    for (let index = 0; index < upload.chunks; index += 1) {
      const start = index * upload.chunk_size;
      const data = await file.slice(start, Math.min(file.size, start + upload.chunk_size)).arrayBuffer();
      hash.update(new Uint8Array(data));
      if (!received.has(index)) {
        await sendChunk(upload.id, index, data, (bytes) => {
          onProgress({ sent: start + bytes, total: file.size, checking: false });
        });
      }
      onProgress({ sent: start + data.byteLength, total: file.size, checking: false });
    }
    onProgress({ sent: file.size, total: file.size, checking: true });
    await request<UploadRead>("POST", `/v1/uploads/${String(upload.id)}/finish`, { sha256: hash.hex() });
  } catch (error) {
    throw failureOf(error);
  }
}
