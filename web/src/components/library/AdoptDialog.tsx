import { useEffect, useRef, useState, type ReactElement } from "react";

import { ApiError } from "../../api/http";
import { adoptFiles, readAdoption, type AdoptionFile, type AdoptionResult } from "../../api/library";
import { texts } from "../../texts";
import { formatSize } from "../../utils/format";
import { dialogBody, dialogFrame } from "../dialog";
import { Spinner } from "../Skeletons";

type Props = {
  readonly seriesId: string;
  /** Le nom de la série : celui des fichiers renommés. */
  readonly name: string;
  readonly onClose: () => void;
  readonly onAdopted: (result: AdoptionResult) => void;
};

type Unit = "volume" | "chapter";

/** Un tome tel que la page le confirme : inclus ou non, son numéro saisi, tome ou chapitre. */
type Row = {
  readonly file: AdoptionFile;
  readonly include: boolean;
  readonly unit: Unit;
  readonly number: string;
};

function rowOf(file: AdoptionFile): Row {
  const chapter = file.chapter !== null;
  const number = chapter ? file.chapter : file.volume;
  return {
    file,
    include: !file.adopted && number !== null,
    unit: chapter ? "chapter" : "volume",
    number: number === null ? "" : String(number),
  };
}

function numberOf(row: Row): number | null {
  const text = row.number.trim().replace(",", ".");
  if (text === "") {
    return null;
  }
  const value = Number(text);
  if (!Number.isFinite(value) || value < 0 || (row.unit === "volume" && !Number.isInteger(value))) {
    return null;
  }
  return value;
}

function baseName(path: string): string {
  return path.slice(path.lastIndexOf("/") + 1);
}

function extensionOf(path: string): string {
  const name = baseName(path);
  const dot = name.lastIndexOf(".");
  return dot <= 0 ? "" : name.slice(dot).toLowerCase();
}

/** Le nom qu'un tome prendrait, comme le rangement l'écrit (« Série - T03.cbz », « Série - Ch. 120.cbz »). */
function targetOf(row: Row, series: string): string | null {
  const value = numberOf(row);
  const proposed = rowOf(row.file);
  if (row.unit === proposed.unit && row.number.trim() === proposed.number) {
    return row.file.target;
  }
  if (value === null) {
    return null;
  }
  const safe = series
    .replace(/[/\\:*?"<>|]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
  const label = row.unit === "volume" ? `T${String(value).padStart(2, "0")}` : `Ch. ${String(value)}`;
  return `${safe} - ${label}${extensionOf(row.file.path)}`;
}

/** L'adoption des fichiers d'une série que shelfdrop n'a pas rangés : l'aperçu, puis la confirmation. */
export function AdoptDialog({ seriesId, name, onClose, onAdopted }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [rows, setRows] = useState<readonly Row[] | null>(null);
  const [workId, setWorkId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
    let stopped = false;
    readAdoption(seriesId).then(
      (read) => {
        if (!stopped) {
          setWorkId(read.workId);
          setRows(read.files.map(rowOf));
        }
      },
      () => {
        if (!stopped) {
          setRows([]);
          setError(texts.adoption.failed);
        }
      },
    );
    return () => {
      stopped = true;
    };
  }, [seriesId]);

  const included = (rows ?? []).filter((row) => row.include);
  const keys = included.map((row) => `${row.unit}:${String(numberOf(row))}`);
  const duplicated = new Set(keys.filter((key, index) => keys.indexOf(key) !== index));
  const blocked = included.some(
    (row) => numberOf(row) === null || duplicated.has(`${row.unit}:${String(numberOf(row))}`),
  );

  function update(itemId: string, change: Partial<Row>): void {
    setRows((current) => (current ?? []).map((row) => (row.file.itemId === itemId ? { ...row, ...change } : row)));
  }

  async function adopt(place: boolean): Promise<void> {
    if (rows === null) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const result = await adoptFiles(
        seriesId,
        rows
          .filter((row) => !row.file.adopted)
          .map((row) => {
            const value = numberOf(row);
            return {
              itemId: row.file.itemId,
              volume: row.unit === "volume" ? value : null,
              chapter: row.unit === "chapter" ? value : null,
              include: row.include,
            };
          }),
        place,
      );
      onAdopted(result);
      ref.current?.close();
    } catch (caught) {
      const reason =
        caught instanceof ApiError && caught.code === "adoption_refused" && typeof caught.data?.["reason"] === "string"
          ? caught.data["reason"]
          : null;
      setError(reason === null ? texts.adoption.failed : (texts.adoption.refused[reason] ?? texts.adoption.failed));
      setPending(false);
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="adopt-title" className={dialogFrame.form64}>
      <div className={dialogBody.tall}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="adopt-title" className="text-lg font-semibold">
            {texts.adoption.title}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">{name}</p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
          {rows === null ? (
            <p role="status" className="flex items-center gap-2 text-sm text-slate-500">
              <Spinner className="size-3.5" /> {texts.adoption.loading}
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-slate-500">{texts.adoption.empty}</p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {rows.map((row) => {
                const file = baseName(row.file.path);
                const target = targetOf(row, name);
                const value = numberOf(row);
                const twice = row.include && duplicated.has(`${row.unit}:${String(value)}`);
                return (
                  <li key={row.file.itemId} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={row.include}
                      disabled={row.file.adopted}
                      onChange={(event) => {
                        update(row.file.itemId, { include: event.target.checked });
                      }}
                      aria-label={texts.adoption.include(file)}
                      className="size-4 accent-accent"
                    />
                    <span className="min-w-0 flex-1 basis-48">
                      <span className="block text-sm wrap-anywhere">{file}</span>
                      <span className="block text-xs text-slate-500">
                        {[
                          row.file.size === null ? "" : formatSize(row.file.size),
                          row.file.origin === "jellyfin"
                            ? texts.adoption.fromJellyfin
                            : row.file.origin === "name"
                              ? texts.adoption.fromName
                              : "",
                          row.file.adopted ? texts.adoption.adopted : "",
                        ]
                          .filter((part) => part !== "")
                          .join(" · ")}
                      </span>
                    </span>
                    <select
                      value={row.unit}
                      disabled={row.file.adopted}
                      onChange={(event) => {
                        update(row.file.itemId, { unit: event.target.value === "chapter" ? "chapter" : "volume" });
                      }}
                      aria-label={texts.adoption.unitFor(file)}
                      className="rounded-md border border-slate-200 bg-surface px-2 py-1 text-sm"
                    >
                      <option value="volume">{texts.adoption.units.volume}</option>
                      <option value="chapter">{texts.adoption.units.chapter}</option>
                    </select>
                    <input
                      value={row.number}
                      disabled={row.file.adopted}
                      placeholder={texts.adoption.unknown}
                      inputMode="decimal"
                      onChange={(event) => {
                        update(row.file.itemId, { number: event.target.value });
                      }}
                      aria-label={texts.adoption.numberFor(file)}
                      aria-invalid={row.include && (value === null || twice)}
                      className={`w-20 rounded-md border px-2 py-1 text-center text-sm outline-none focus:border-accent ${
                        row.include && (value === null || twice) ? "border-rose-400" : "border-slate-200"
                      }`}
                    />
                    <span className="w-full text-xs wrap-anywhere text-slate-500 md:w-auto md:basis-56">
                      {row.file.adopted
                        ? null
                        : twice
                          ? texts.adoption.duplicate
                          : `${texts.adoption.target} : ${target ?? texts.adoption.unknown}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          {rows !== null && rows.length > 0 && workId === null ? (
            <p className="mt-3 text-sm text-amber-800">{texts.adoption.noWork}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {error !== null ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {error}
            </p>
          ) : blocked ? (
            <p role="status" className="mr-auto text-sm text-slate-500">
              {texts.adoption.blocked}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => {
              ref.current?.close();
            }}
            className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            {texts.dialog.cancel}
          </button>
          <button
            type="button"
            disabled={pending || blocked || included.length === 0 || workId === null}
            onClick={() => {
              void adopt(false);
            }}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {texts.adoption.adopt}
          </button>
          <button
            type="button"
            disabled={pending || blocked || included.length === 0 || workId === null}
            onClick={() => {
              void adopt(true);
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {texts.adoption.adoptAndPlace}
          </button>
        </div>
      </div>
    </dialog>
  );
}
