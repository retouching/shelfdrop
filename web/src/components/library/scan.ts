import type { ScanMode } from "../../api/library";

/** Les modes de rescan Jellyfin : nouveaux fichiers seuls, champs vides, ou tout remplacer. */
export type { ScanMode };
export const scanModes: readonly ScanMode[] = ["new", "missing", "all"];
