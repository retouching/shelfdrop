import { useEffect, useRef, useState, type ReactElement } from "react";

import { ApiError } from "../../api/http";
import {
  base64Of,
  changeSeries,
  itemImage,
  readProposals,
  readScan,
  startScan,
  type ImageChoice,
  type Proposals,
  type Series,
} from "../../api/library";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { field } from "../WorkPicker";
import { Cover } from "./Cover";
import { scanModes, type ScanMode } from "./scan";

type Props = {
  readonly series: Series;
  readonly onClose: () => void;
  readonly onApplied: (next: Series) => void;
  readonly onRescanned: (name: string) => void;
};

type Fields = {
  readonly name: string;
  readonly originalTitle: string;
  readonly authors: string;
  readonly year: string;
  readonly genres: string;
  readonly summary: string;
};

// Une image envoyée de plus de 5 Mo est refusée par l'API.
const IMAGE_MAX_BYTES = 5 * 1024 * 1024;

function fieldsOf(series: Series): Fields {
  return {
    name: series.name,
    originalTitle: series.originalTitle,
    authors: series.authors.join(", "),
    year: series.year === null ? "" : String(series.year),
    genres: series.genres.join(", "),
    summary: series.summary,
  };
}

function listOf(text: string): readonly string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/** Image choisie : l'actuelle, celle d'un tome, d'une source, d'un lien ou d'un fichier envoyé. */
type Choice =
  | { readonly kind: "current" }
  | { readonly kind: "item"; readonly itemId: string }
  | { readonly kind: "url"; readonly url: string }
  | { readonly kind: "file"; readonly name: string; readonly data: string; readonly preview: string };

function previewOf(series: Series, choice: Choice): string | null {
  switch (choice.kind) {
    case "current":
      return series.hasImage ? itemImage(series.id, 600) : null;
    case "item":
      return itemImage(choice.itemId, 600);
    case "url":
      return choice.url;
    case "file":
      return choice.preview;
  }
}

function imageOf(choice: Choice): ImageChoice | null {
  switch (choice.kind) {
    case "current":
      return null;
    case "item":
      return { kind: "item", itemId: choice.itemId };
    case "url":
      return { kind: "url", url: choice.url };
    case "file":
      return { kind: "data", data: choice.data };
  }
}

export function SeriesEditor({ series, onClose, onApplied, onRescanned }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const initial = fieldsOf(series);
  const [fields, setFields] = useState<Fields>(initial);
  const [image, setImage] = useState<Choice>({ kind: "current" });
  const [url, setUrl] = useState("");
  const [toSeries, setToSeries] = useState(true);
  const [toVolumes, setToVolumes] = useState(true);
  const [summaryToVolumes, setSummaryToVolumes] = useState(series.volumesWithoutSummary > 0);
  const [lock, setLock] = useState(true);
  const [saveCover, setSaveCover] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rescanning, setRescanning] = useState(false);
  const [scanMode, setScanMode] = useState<ScanMode>("missing");
  const [proposals, setProposals] = useState<Proposals | null>(null);

  useEffect(() => {
    ref.current?.showModal();
    let stopped = false;
    readProposals(series.id)
      .then((read) => {
        if (!stopped) {
          setProposals(read);
        }
      })
      .catch(() => {
        if (!stopped) {
          setProposals({ volumes: [], covers: [], summaries: [] });
        }
      });
    return () => {
      stopped = true;
    };
  }, [series.id]);

  async function rescan(): Promise<void> {
    setRescanning(true);
    setError(null);
    try {
      await startScan(scanMode, { seriesId: series.id });
      // Jellyfin ne suit pas le scan d'une série : celui de sa bibliothèque en tient lieu.
      for (let reads = 0; reads < 30; reads += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const progress = await readScan();
        if (progress[series.kind] === null || progress[series.kind] === undefined) {
          break;
        }
      }
      setFields(initial);
      setImage({ kind: "current" });
      onRescanned(series.name);
    } catch {
      setError(texts.library.unavailable);
    } finally {
      setRescanning(false);
    }
  }

  const proposedSummary = proposals?.summaries[0] ?? null;
  const changed =
    (Object.keys(initial) as (keyof Fields)[]).filter((key) => fields[key] !== initial[key]).length +
    (image.kind === "current" ? 0 : 1);

  function set(key: keyof Fields, value: string): void {
    setFields((current) => ({ ...current, [key]: value }));
  }

  async function apply(): Promise<void> {
    setPending(true);
    setError(null);
    const year = Number.parseInt(fields.year, 10);
    try {
      const next = await changeSeries(series.id, {
        name: fields.name.trim() === "" ? series.name : fields.name.trim(),
        originalTitle: fields.originalTitle,
        authors: listOf(fields.authors),
        year: Number.isNaN(year) ? null : year,
        genres: listOf(fields.genres),
        summary: fields.summary,
        lock,
        summaryToVolumes: fields.summary !== "" && summaryToVolumes,
        image: imageOf(image),
        imageToSeries: toSeries,
        imageToVolumes: toVolumes,
        saveCover,
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

  async function pickFile(file: File): Promise<void> {
    if (file.size > IMAGE_MAX_BYTES) {
      setError(texts.editor.tooLarge);
      return;
    }
    setError(null);
    const data = await base64Of(file);
    // La politique des images de la page prend les adresses data:, pas blob:.
    setImage({ kind: "file", name: file.name, data, preview: `data:${file.type};base64,${data}` });
  }

  const input = (key: keyof Fields, label: string, wide = false): ReactElement => (
    <label className={`block space-y-1.5 ${wide ? "sm:col-span-2" : ""}`}>
      <span className="text-sm font-medium">{label}</span>
      <input
        value={fields[key]}
        onChange={(event) => {
          set(key, event.target.value);
        }}
        inputMode={key === "year" ? "numeric" : undefined}
        className={`${field} ${fields[key] === initial[key] ? "" : "border-accent"}`}
      />
    </label>
  );

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="editor-title"
      className="m-auto max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="flex max-h-[calc(92vh-2px)] flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div>
            <h2 id="editor-title" className="text-lg font-semibold">
              {texts.editor.title}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {series.name} · {texts.library.libraries[series.kind]} · {texts.library.volumes(series.volumes)}
            </p>
          </div>
          <span className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
              onClick={() => {
                setFields(initial);
                setImage({ kind: "current" });
              }}
            >
              {texts.editor.refresh}
            </button>
            <label className="text-sm">
              <span className="sr-only">{texts.scan.mode}</span>
              <select
                value={scanMode}
                disabled={rescanning}
                onChange={(event) => {
                  setScanMode(event.target.value as ScanMode);
                }}
                className="rounded-lg border border-slate-200 bg-surface px-2 py-1.5 text-sm"
              >
                {scanModes.map((mode) => (
                  <option key={mode} value={mode}>
                    {texts.scan.modes[mode]}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={rescanning}
              onClick={() => {
                void rescan();
              }}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:cursor-wait"
            >
              {rescanning ? <Spinner className="size-3.5" /> : null}
              {texts.scan.series}
            </button>
          </span>
        </div>

        <div className="grid min-h-0 flex-1 gap-8 overflow-y-auto px-6 py-5 md:grid-cols-[18rem_1fr]">
          <section aria-labelledby="editor-image" className="space-y-4">
            <h3 id="editor-image" className="text-sm font-semibold">
              {texts.editor.image}
            </h3>
            <Cover src={previewOf(series, image)} label={fields.name} className="h-96 w-64" />

            <div>
              <p className="mb-2 text-xs text-slate-500">{texts.editor.proposals}</p>
              <ul className="grid grid-cols-4 gap-2">
                <li>
                  <ImageButton
                    active={image.kind === "current"}
                    label={texts.editor.current}
                    caption={texts.editor.current}
                    src={series.hasImage ? itemImage(series.id, 200) : null}
                    title={series.name}
                    onClick={() => {
                      setImage({ kind: "current" });
                    }}
                  />
                </li>
                {proposals?.volumes.map((volume) => (
                  <li key={volume.itemId}>
                    <ImageButton
                      active={image.kind === "item" && image.itemId === volume.itemId}
                      label={volume.label}
                      caption={volume.label}
                      src={itemImage(volume.itemId, 200)}
                      title={series.name}
                      onClick={() => {
                        setImage({ kind: "item", itemId: volume.itemId });
                      }}
                    />
                  </li>
                ))}
                {proposals?.covers.map((cover) => (
                  <li key={cover.url}>
                    <ImageButton
                      active={image.kind === "url" && image.url === cover.url}
                      label={cover.source}
                      caption={cover.source}
                      src={cover.url}
                      title={series.name}
                      onClick={() => {
                        setImage({ kind: "url", url: cover.url });
                      }}
                    />
                  </li>
                ))}
              </ul>
              {proposals === null ? (
                <p role="status" className="mt-2 flex items-center gap-2 text-xs text-slate-500">
                  <Spinner className="size-3" /> {texts.editor.proposalsLoading}
                </p>
              ) : proposals.volumes.length + proposals.covers.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500">{texts.editor.noProposals}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="block space-y-1.5">
                <span className="text-xs text-slate-500">{texts.editor.fromUrl}</span>
                <span className="flex gap-2">
                  <input
                    value={url}
                    onChange={(event) => {
                      setUrl(event.target.value);
                    }}
                    placeholder={texts.editor.fromUrlPlaceholder}
                    className={field}
                  />
                  <button
                    type="button"
                    disabled={!/^https?:\/\//.test(url)}
                    onClick={() => {
                      setImage({ kind: "url", url });
                    }}
                    className="shrink-0 rounded-lg border border-slate-200 px-3 text-sm hover:bg-slate-50 disabled:opacity-50"
                  >
                    {texts.editor.useUrl}
                  </button>
                </span>
              </label>
              <label className="flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                {image.kind === "file" ? image.name : texts.editor.upload}
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
            </div>

            {image.kind === "current" ? null : (
              <fieldset className="space-y-1.5 text-sm">
                <legend className="mb-1 text-xs text-slate-500">{texts.editor.applyTo}</legend>
                <Check checked={toSeries} onChange={setToSeries} label={texts.editor.applyToSeries} />
                <Check
                  checked={toVolumes}
                  onChange={setToVolumes}
                  label={`${texts.editor.applyToVolumes} (${String(series.volumesWithoutImage)})`}
                />
                <Check checked={saveCover} onChange={setSaveCover} label={texts.editor.saveCover} />
              </fieldset>
            )}
          </section>

          <section className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {input("name", texts.editor.name)}
              {input("originalTitle", texts.editor.originalTitle)}
              {input("authors", texts.editor.authors)}
              {input("year", texts.editor.year)}
              {input("genres", texts.editor.genres, true)}
            </div>
            <label className="block space-y-1.5">
              <span className="flex items-center justify-between text-sm font-medium">
                {texts.editor.summary}
                {proposedSummary === null || fields.summary !== "" ? null : (
                  <span className="text-xs font-normal text-slate-500">
                    {texts.editor.summaryFrom(proposedSummary.source)}
                  </span>
                )}
              </span>
              <textarea
                value={fields.summary}
                onChange={(event) => {
                  set("summary", event.target.value);
                }}
                rows={6}
                placeholder={proposedSummary?.text}
                className={`${field} resize-y ${fields.summary === initial.summary ? "" : "border-accent"}`}
              />
            </label>
            {proposedSummary === null || fields.summary !== "" ? null : (
              <button
                type="button"
                onClick={() => {
                  set("summary", proposedSummary.text);
                }}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
              >
                {texts.editor.useSummary}
              </button>
            )}
            <div className="space-y-1.5 border-t border-slate-100 pt-4 text-sm">
              {series.volumesWithoutSummary === 0 ? null : (
                <Check
                  checked={summaryToVolumes}
                  onChange={setSummaryToVolumes}
                  label={`${texts.editor.summaryToVolumes} (${String(series.volumesWithoutSummary)})`}
                />
              )}
              <Check checked={lock} onChange={setLock} label={texts.editor.lock} hint={texts.editor.lockHint} />
            </div>
          </section>
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-6 py-4">
          {error === null ? (
            <span className="text-sm text-slate-500">{changed === 0 ? null : texts.editor.changed(changed)}</span>
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
              disabled={changed === 0 || pending}
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
      </div>
    </dialog>
  );
}

function ImageButton({
  active,
  label,
  caption,
  src,
  title,
  onClick,
}: {
  readonly active: boolean;
  readonly label: string;
  readonly caption: string;
  readonly src: string | null;
  readonly title: string;
  readonly onClick: () => void;
}): ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className="w-full space-y-1 text-left"
    >
      <span
        className={`block rounded-lg p-0.5 ${active ? "ring-2 ring-accent" : "ring-1 ring-transparent hover:ring-slate-300"}`}
      >
        <Cover src={src} label={title} className="aspect-[2/3] w-full" bare />
      </span>
      <span className={`block truncate text-[11px] ${active ? "text-accent-text" : "text-slate-500"}`}>{caption}</span>
    </button>
  );
}

function Check({
  checked,
  onChange,
  label,
  hint,
}: {
  readonly checked: boolean;
  readonly onChange: (value: boolean) => void;
  readonly label: string;
  readonly hint?: string;
}): ReactElement {
  return (
    <label className="flex items-start gap-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
        className="mt-0.5 size-4 accent-accent"
      />
      <span>
        {label}
        {hint === undefined ? null : <span className="block text-xs text-slate-500">{hint}</span>}
      </span>
    </label>
  );
}
