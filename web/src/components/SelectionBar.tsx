import type { ReactElement } from "react";

import { texts } from "../texts";
import { DownloadIcon } from "./icons";

type Props = {
  readonly count: number;
  readonly coverage: string;
  readonly onClear: () => void;
  readonly onDownload: () => void;
};

/** Barre fixée en bas de l'écran tant qu'une release est sélectionnée. */
export function SelectionBar({ count, coverage, onClear, onDownload }: Props): ReactElement | null {
  if (count === 0) {
    return null;
  }
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-1 bg-accent px-4 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] text-white shadow-lg md:sticky md:bottom-4 md:z-10 md:mx-auto md:max-w-3xl md:flex-nowrap md:rounded-xl md:px-5 md:py-3">
      <p className="min-w-0 flex-1 basis-full text-sm md:basis-0" aria-live="polite">
        {texts.results.selected(count, coverage)}
      </p>
      <button type="button" onClick={onClear} className="text-sm text-white/70 hover:text-white">
        {texts.results.clear}
      </button>
      <button
        type="button"
        onClick={onDownload}
        className="flex items-center gap-2 rounded-lg bg-surface px-4 py-1.5 text-sm font-medium text-ink hover:bg-accent-soft"
      >
        <DownloadIcon />
        {texts.results.download}
      </button>
    </div>
  );
}
