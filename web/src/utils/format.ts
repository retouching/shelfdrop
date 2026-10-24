// Formatages purs, sans dépendance au domaine, dans la langue de la page.
import { locale, texts } from "../texts";

export function formatSize(bytes: number): string {
  if (bytes >= 1_000_000_000) {
    return texts.units.gigabytes((bytes / 1_000_000_000).toLocaleString(locale, { maximumFractionDigits: 1 }));
  }
  return texts.units.megabytes(Math.max(1, Math.round(bytes / 1_000_000)).toLocaleString(locale));
}

export function formatSpeed(bytesPerSecond: number): string {
  return texts.units.speed((bytesPerSecond / 1_000_000).toLocaleString(locale, { maximumFractionDigits: 1 }));
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return texts.units.seconds(Math.max(1, Math.round(seconds)));
  }
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? texts.units.minutes(minutes) : texts.units.hours(Math.floor(minutes / 60), minutes % 60);
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
