/** Les modes de rescan Jellyfin : nouveaux fichiers seuls, champs vides, ou tout remplacer. */
export type ScanMode = "new" | "missing" | "all";
export const scanModes: readonly ScanMode[] = ["new", "missing", "all"];
