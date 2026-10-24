import { useEffect, useRef, useState, type ReactElement } from "react";

import { ApiError } from "../../api/http";
import { base64Of, changeVolume, itemImage, type ImageChoice, type Volume } from "../../api/library";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { field } from "../WorkPicker";
import { Cover } from "./Cover";

type Props = {
  readonly volume: Volume;
  readonly onClose: () => void;
  readonly onApplied: (next: Volume) => void;
};

// Une image envoyée de plus de 5 Mo est refusée par l'API.
const IMAGE_MAX_BYTES = 5 * 1024 * 1024;

function listOf(text: string): readonly string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/** Fiche d'un tome : titre, numéro, auteurs, résumé et image, écrits dans Jellyfin. */
export function VolumeEditor({ volume, onClose, onApplied }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(volume.name);
  const [number, setNumber] = useState(volume.number === null ? "" : String(volume.number));
  const [authors, setAuthors] = useState(volume.authors.join(", "));
  const [summary, setSummary] = useState(volume.summary);
  const [url, setUrl] = useState("");
  const [image, setImage] = useState<{ readonly choice: ImageChoice; readonly preview: string } | null>(null);
  const [lock, setLock] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function pickFile(file: File): Promise<void> {
    if (file.size > IMAGE_MAX_BYTES) {
      setError(texts.editor.tooLarge);
      return;
    }
    setError(null);
    const data = await base64Of(file);
    setImage({ choice: { kind: "data", data }, preview: `data:${file.type};base64,${data}` });
  }

  async function apply(): Promise<void> {
    setPending(true);
    setError(null);
    const parsed = Number.parseInt(number, 10);
    try {
      const next = await changeVolume(volume.id, {
        name: name.trim() === "" ? volume.name : name.trim(),
        number: Number.isNaN(parsed) ? null : parsed,
        summary,
        authors: listOf(authors),
        lock,
        image: image?.choice ?? null,
      });
      onApplied(next);
      ref.current?.close();
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.code === "image_refused"
          ? texts.editor.imageRefused
          : texts.library.failed,
      );
      setPending(false);
    }
  }

  const preview = image?.preview ?? (volume.hasImage ? itemImage(volume.id, volume.imageTag, 400) : null);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="volume-title"
      className="m-auto max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 id="volume-title" className="text-lg font-semibold">
          {texts.volumes.editorTitle}
        </h2>
        <p className="mt-0.5 text-sm text-slate-500">{volume.fileName}</p>
      </div>
      <div className="grid gap-6 px-6 py-5 sm:grid-cols-[10rem_1fr]">
        <div className="space-y-3">
          <span className="block text-sm font-medium">{texts.volumes.image}</span>
          <Cover src={preview} label={name} className="h-60 w-40" />
          <span className="flex gap-2">
            <input
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
              }}
              aria-label={texts.editor.fromUrl}
              placeholder={texts.editor.fromUrlPlaceholder}
              className={field}
            />
            <button
              type="button"
              disabled={!/^https?:\/\//.test(url)}
              onClick={() => {
                setImage({ choice: { kind: "url", url }, preview: url });
              }}
              className="shrink-0 rounded-lg border border-slate-200 px-2 text-sm hover:bg-slate-50 disabled:opacity-50"
            >
              {texts.editor.useUrl}
            </button>
          </span>
          <label className="flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
            {texts.editor.upload}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file !== undefined) {
                  void pickFile(file);
                }
              }}
            />
          </label>
          {image === null ? null : (
            <button
              type="button"
              onClick={() => {
                setImage(null);
              }}
              className="w-full rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              {texts.volumes.keepImage}
            </button>
          )}
        </div>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[1fr_7rem]">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">{texts.volumes.name}</span>
              <input
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                }}
                className={field}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">{texts.volumes.numberLabel}</span>
              <input
                value={number}
                inputMode="numeric"
                onChange={(event) => {
                  setNumber(event.target.value);
                }}
                className={field}
              />
            </label>
          </div>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{texts.volumes.authors}</span>
            <input
              value={authors}
              onChange={(event) => {
                setAuthors(event.target.value);
              }}
              className={field}
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{texts.volumes.summary}</span>
            <textarea
              value={summary}
              rows={6}
              onChange={(event) => {
                setSummary(event.target.value);
              }}
              className={`${field} resize-y`}
            />
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={lock}
              onChange={(event) => {
                setLock(event.target.checked);
              }}
              className="mt-0.5 size-4 accent-accent"
            />
            <span>
              {texts.volumes.lock}
              <span className="block text-xs text-slate-500">{texts.editor.lockHint}</span>
            </span>
          </label>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-6 py-4">
        {error === null ? (
          <span />
        ) : (
          <p role="alert" className="text-sm text-rose-700">
            {error}
          </p>
        )}
        <span className="flex gap-2">
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
            disabled={pending}
            onClick={() => {
              void apply();
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {pending ? texts.library.applying : texts.editor.apply}
          </button>
        </span>
      </div>
    </dialog>
  );
}
