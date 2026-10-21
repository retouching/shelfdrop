// Formatages purs, sans dépendance au domaine.
export function formatSize(bytes: number): string {
  if (bytes >= 1_000_000_000) {
    return `${(bytes / 1_000_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Go`;
  }
  return `${Math.max(1, Math.round(bytes / 1_000_000)).toLocaleString("fr-FR")} Mo`;
}
