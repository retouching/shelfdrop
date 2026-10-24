import { createContext, use } from "react";

import type { ShelfFile } from "../types";

/** Ce que le cadre (App) tient pour une page chargée à la demande. */
export type Shell = {
  /** Les fichiers de Ranger, avec les envois de la page Manuel pas encore listés. */
  readonly placeFiles: readonly ShelfFile[];
  readonly refreshPlace: (file: ShelfFile) => void;
};

export const ShellContext = createContext<Shell | null>(null);

export function useShell(): Shell {
  const shell = use(ShellContext);
  if (shell === null) {
    throw new Error("A page is rendered outside the frame");
  }
  return shell;
}
