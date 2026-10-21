// Formatages purs, sans dépendance au domaine.
export function formatSize(bytes: number): string {
  if (bytes >= 1_000_000_000) {
    return `${(bytes / 1_000_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Go`;
  }
  return `${Math.max(1, Math.round(bytes / 1_000_000)).toLocaleString("fr-FR")} Mo`;
}

export function formatSpeed(bytesPerSecond: number): string {
  return `${(bytesPerSecond / 1_000_000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo/s`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${String(Math.max(1, Math.round(seconds)))} s`;
  }
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `${String(minutes)} min` : `${String(Math.floor(minutes / 60))} h ${String(minutes % 60)}`;
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
