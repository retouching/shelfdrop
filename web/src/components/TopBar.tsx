import type { ReactElement } from "react";

import { texts } from "../texts";
import { MenuIcon, ShelfIcon } from "./icons";

type Props = {
  readonly title: string;
  /** L'identifiant de la barre de navigation que le bouton ouvre. */
  readonly controls: string;
  readonly open: boolean;
  /** Un compteur ou une alerte de la barre : un point sur le bouton. */
  readonly alert: boolean;
  readonly onMenu: () => void;
};

/** La barre du haut des petits écrans : le nom, la section, et le bouton de la navigation. */
export function TopBar({ title, controls, open, alert, onMenu }: Props): ReactElement {
  return (
    <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-slate-200 bg-surface px-2 py-1.5 md:hidden">
      <button
        type="button"
        onClick={onMenu}
        aria-expanded={open}
        aria-controls={controls}
        aria-label={texts.nav.menu}
        className="relative flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-ink"
      >
        <MenuIcon className="size-5" />
        {alert ? <span aria-hidden="true" className="absolute top-2 right-2 size-2 rounded-full bg-rose-500" /> : null}
      </button>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white">
        <ShelfIcon className="size-4" />
      </span>
      <p className="min-w-0 flex-1 truncate text-sm">
        <span className="font-semibold text-ink">{texts.appName}</span>
        <span className="px-1.5 text-slate-400">›</span>
        <span className="text-slate-600">{title}</span>
      </p>
    </div>
  );
}
