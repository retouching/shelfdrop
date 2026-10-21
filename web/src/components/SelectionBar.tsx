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
    <div className="sticky bottom-4 z-10 mx-auto flex max-w-3xl items-center gap-4 rounded-xl bg-accent px-5 py-3 text-white shadow-lg">
      <p className="flex-1 text-sm" aria-live="polite">
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
