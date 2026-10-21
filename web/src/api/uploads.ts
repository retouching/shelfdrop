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

async function sendChunk(id: number, index: number, data: ArrayBuffer): Promise<void> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      const response = await fetch(`/api/v1/uploads/${String(id)}/chunks/${String(index)}`, {
        method: "PUT",
        headers: { Accept: "application/json", "Content-Type": "application/octet-stream" },
        body: data,
      });
      if (response.ok) {
        return;
      }
      if (response.status < 500 && response.status !== 429) {
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

/** Le fichier envoyé par morceaux (ceux déjà reçus sont sautés), puis vérifié par le serveur.
 * `onProgress` reçoit le pourcentage envoyé. Lève UploadError. */
export async function uploadFile(file: File, onProgress: (percent: number) => void): Promise<void> {
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
        await sendChunk(upload.id, index, data);
      }
      onProgress(Math.min(99, Math.round(((index + 1) / upload.chunks) * 100)));
    }
    await request<UploadRead>("POST", `/v1/uploads/${String(upload.id)}/finish`, { sha256: hash.hex() });
    onProgress(100);
  } catch (error) {
    throw failureOf(error);
  }
}
