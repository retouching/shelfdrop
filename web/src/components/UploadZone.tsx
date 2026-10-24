import { useEffect, useRef, useState, type ReactElement } from "react";

import { texts } from "../texts";
import { DownloadIcon } from "./icons";

const accept = ".epub,.pdf,.cbz,.cbr,.m4b,.mp3,.zip";

type Props = {
  readonly onFiles: (files: readonly File[]) => void;
};

/** Envoi de fichiers : glisser-déposer ou bouton. Les fichiers envoyés arrivent dans Ranger. */
export function UploadZone({ onFiles }: Props): ReactElement {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLElement>(null);
  const onFilesRef = useRef(onFiles);
  useEffect(() => {
    onFilesRef.current = onFiles;
  });

  function addFiles(list: FileList | null | undefined): void {
    if (list !== null && list !== undefined && list.length > 0) {
      onFilesRef.current([...list]);
    }
  }

  // Glisser-déposer : écouteurs posés à la main, la zone reste une région et non un faux bouton.
  // Le bouton « Choisir des fichiers » garde l'accès au clavier.
  useEffect(() => {
    const zone = dropRef.current;
    if (zone === null) {
      return undefined;
    }
    const over = (event: DragEvent): void => {
      event.preventDefault();
      setDragging(true);
    };
    const leave = (): void => {
      setDragging(false);
    };
    const drop = (event: DragEvent): void => {
      event.preventDefault();
      setDragging(false);
      addFiles(event.dataTransfer?.files);
    };
    zone.addEventListener("dragover", over);
    zone.addEventListener("dragleave", leave);
    zone.addEventListener("drop", drop);
    return () => {
      zone.removeEventListener("dragover", over);
      zone.removeEventListener("dragleave", leave);
      zone.removeEventListener("drop", drop);
    };
  }, []);

  return (
    <section
      ref={dropRef}
      aria-label={texts.place.dropTitle}
      className={`flex flex-wrap items-center gap-4 rounded-xl border-2 border-dashed px-4 py-4 transition md:px-5 ${
        dragging ? "border-accent bg-accent-soft" : "border-slate-300 bg-surface"
      }`}
    >
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent-text">
        <DownloadIcon className="size-5 rotate-180" />
      </span>
      <span className="min-w-0 flex-1 sm:min-w-60">
        <span className="block font-semibold text-ink">{texts.place.dropTitle}</span>
        <span className="block text-sm text-slate-500">{texts.place.dropHint}</span>
      </span>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="w-full rounded-lg border border-transparent bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong sm:w-auto"
      >
        {texts.place.dropButton}
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        aria-label={texts.place.dropButton}
        className="sr-only"
        onChange={(event) => {
          addFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </section>
  );
}
