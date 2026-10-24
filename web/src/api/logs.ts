// Les journaux de l'API et du worker de rangement, lus page par page, les plus récents d'abord.
import { request } from "./http";

export type LogService = "api" | "placement";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type LogEntry = {
  /** UTC, ISO 8601, à la milliseconde. */
  readonly timestamp: string;
  readonly level: string;
  readonly logger: string;
  readonly message: string;
  readonly requestId: string | null;
  /** Les autres champs de l'entrée : ses champs propres, `exception`, `stack`. */
  readonly fields: Readonly<Record<string, unknown>>;
};

export type LogFilters = {
  readonly service: LogService;
  readonly level: LogLevel;
  readonly text: string;
};

type LogEntryRead = {
  readonly timestamp: string;
  readonly level: string;
  readonly logger: string;
  readonly message: string;
  readonly request_id: string | null;
  readonly fields: Readonly<Record<string, unknown>>;
};

/** Les entrées, et le curseur des plus anciennes (null : il n'y en a plus). */
export async function readLogs(
  filters: LogFilters,
  before: string | null,
  limit = 200,
): Promise<{ readonly entries: readonly LogEntry[]; readonly next: string | null }> {
  const params = new URLSearchParams({ service: filters.service, level: filters.level, limit: String(limit) });
  const text = filters.text.trim();
  if (text !== "") {
    params.set("text", text);
  }
  if (before !== null) {
    params.set("before", before);
  }
  const body = await request<{ readonly entries: readonly LogEntryRead[]; readonly next: string | null }>(
    "GET",
    `/v1/logs?${params.toString()}`,
  );
  return {
    entries: body.entries.map((read) => ({
      timestamp: read.timestamp,
      level: read.level,
      logger: read.logger,
      message: read.message,
      requestId: read.request_id,
      fields: read.fields,
    })),
    next: body.next,
  };
}
