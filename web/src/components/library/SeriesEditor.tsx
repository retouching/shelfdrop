import { useEffect, useRef, useState, type ReactElement } from "react";

import { wait } from "../../mock/latency";
import type { Series } from "../../mock/library";
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

type Fields = Pick<Series, "name" | "originalTitle" | "authors" | "genres" | "summary"> & { readonly year: string };

function fieldsOf(series: Series): Fields {
  return {
    name: series.name,
    originalTitle: series.originalTitle,
    authors: series.authors,
    year: series.year === null ? "" : String(series.year),
    genres: series.genres,
    summary: series.summary,
  };
}

/** Image choisie : la vignette d'une source, un lien ou un fichier envoyé. */
type ImageChoice =
  | { readonly kind: "current" }
  | { readonly kind: "proposal"; readonly id: string; readonly hue: number }
  | { readonly kind: "url"; readonly url: string }
  | { readonly kind: "file"; readonly name: string };

function choiceHue(series: Series, choice: ImageChoice): number | null {
  switch (choice.kind) {
    case "current":
      return series.hasImage ? series.hue : null;
    case "proposal":
      return choice.hue;
    case "url":
    case "file":
      return (series.hue + 180) % 360;
  }
}

export function SeriesEditor({ series, onClose, onApplied, onRescanned }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const initial = fieldsOf(series);
  const [fields, setFields] = useState<Fields>(initial);
  const [image, setImage] = useState<ImageChoice>({ kind: "current" });
  const [url, setUrl] = useState("");
  const [toSeries, setToSeries] = useState(true);
  const [toVolumes, setToVolumes] = useState(true);
  const [summaryToVolumes, setSummaryToVolumes] = useState(series.volumesWithoutSummary > 0);
  const [lock, setLock] = useState(true);
  const [saveCover, setSaveCover] = useState(true);
  const [pending, setPending] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [scanMode, setScanMode] = useState<ScanMode>("missing");

  async function rescan(): Promise<void> {
    setRescanning(true);
    await wait(1500);
    setRescanning(false);
    setFields(initial);
    setImage({ kind: "current" });
    onRescanned(series.name);
  }

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  const changed =
    (Object.keys(initial) as (keyof Fields)[]).filter((key) => fields[key] !== initial[key]).length +
    (image.kind === "current" ? 0 : 1);

  function set(key: keyof Fields, value: string): void {
    setFields((current) => ({ ...current, [key]: value }));
  }

  async function apply(): Promise<void> {
    setPending(true);
    await wait(900);
    const hue = choiceHue(series, image);
    onApplied({
      ...series,
      ...fields,
      year: fields.year === "" ? null : Number(fields.year),
      hasImage: image.kind === "current" ? series.hasImage : toSeries || series.hasImage,
      hue: image.kind === "current" || !toSeries ? series.hue : (hue ?? series.hue),
      volumesWithoutSummary: fields.summary !== "" && summaryToVolumes ? 0 : series.volumesWithoutSummary,
      proposedSummary: fields.summary === "" ? series.proposedSummary : null,
    });
    ref.current?.close();
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
      className="m-auto max-h-[92vh] w-full max-w-5xl rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="flex max-h-[92vh] flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div>
            <h2 id="editor-title" className="text-lg font-semibold">
              {texts.editor.title}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {series.name} · {texts.library.libraries[series.library]} · {texts.library.volumes(series.volumes)}
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
            <Cover hue={choiceHue(series, image)} label={fields.name} className="h-96 w-64" />

            <div>
              <p className="mb-2 text-xs text-slate-500">{texts.editor.proposals}</p>
              <ul className="grid grid-cols-4 gap-2">
                <li>
                  <ImageButton
                    active={image.kind === "current"}
                    label={texts.editor.current}
                    caption={texts.editor.current}
                    hue={series.hasImage ? series.hue : null}
                    title={series.name}
                    onClick={() => {
                      setImage({ kind: "current" });
                    }}
                  />
                </li>
                {series.covers.map((cover) => (
                  <li key={cover.id}>
                    <ImageButton
                      active={image.kind === "proposal" && image.id === cover.id}
                      label={`${cover.source} · ${String(cover.width)}×${String(cover.height)}`}
                      caption={cover.source}
                      hue={cover.hue}
                      title={series.name}
                      onClick={() => {
                        setImage({ kind: "proposal", id: cover.id, hue: cover.hue });
                      }}
                    />
                  </li>
                ))}
              </ul>
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
                    disabled={!url.startsWith("http")}
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
                  accept="image/*"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file !== undefined) {
                      setImage({ kind: "file", name: file.name });
                    }
                  }}
                />
              </label>
            </div>

            {image.kind === "current" ? null : (
              <fieldset className="space-y-1.5 text-sm">
                <legend className="mb-1 text-xs text-slate-500">{texts.editor.applyTo}</legend>
                <Check checked={toSeries} onChange={setToSeries} label={texts.editor.applyToSeries} />
                <Check checked={toVolumes} onChange={setToVolumes} label={texts.editor.applyToVolumes} />
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
                {series.proposedSummary === null || fields.summary !== "" ? null : (
                  <span className="text-xs font-normal text-slate-500">
                    {texts.editor.summaryFrom(series.proposedSummary.source)}
                  </span>
                )}
              </span>
              <textarea
                value={fields.summary}
                onChange={(event) => {
                  set("summary", event.target.value);
                }}
                rows={6}
                placeholder={series.proposedSummary?.text}
                className={`${field} resize-y ${fields.summary === initial.summary ? "" : "border-accent"}`}
              />
            </label>
            {series.proposedSummary === null || fields.summary !== "" ? null : (
              <button
                type="button"
                onClick={() => {
                  set("summary", series.proposedSummary?.text ?? "");
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
          <span className="text-sm text-slate-500">{changed === 0 ? null : texts.editor.changed(changed)}</span>
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
              className="flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
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
  hue,
  title,
  onClick,
}: {
  readonly active: boolean;
  readonly label: string;
  readonly caption: string;
  readonly hue: number | null;
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
        <Cover hue={hue} label={title} className="aspect-[2/3] w-full" bare />
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
