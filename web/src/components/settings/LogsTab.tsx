// Rubrique Journaux : les entrées de l'API et du worker de rangement, filtrées, les plus récentes
// d'abord, relues à la demande ou toutes les quelques secondes, page par page vers les plus anciennes.
import { useEffect, useState, type ReactElement } from "react";

import { readLogs, type LogEntry, type LogFilters, type LogLevel, type LogService } from "../../api/logs";
import { texts } from "../../texts";
import { RefreshBar } from "../RefreshBar";
import { Spinner } from "../Skeletons";
import { Card, Field, input } from "./parts";

const services: readonly LogService[] = ["api", "placement"];

const levels: readonly LogLevel[] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

const levelStyles: Readonly<Record<LogLevel, string>> = {
  DEBUG: "bg-slate-100 text-slate-600",
  INFO: "bg-sky-50 text-sky-700",
  WARNING: "bg-amber-50 text-amber-800",
  ERROR: "bg-rose-50 text-rose-700",
  CRITICAL: "bg-rose-600 text-white",
};

function isLevel(value: string): value is LogLevel {
  return (levels as readonly string[]).includes(value);
}

function levelLabel(level: string): string {
  return isLevel(level) ? texts.logs.levels[level] : level;
}

/** « 24/10 18:42:07.123 », à l'heure du navigateur. */
function timeOf(timestamp: string): string {
  const date = new Date(timestamp);
  const day = date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
  const clock = date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return `${day} ${clock}.${String(date.getMilliseconds()).padStart(3, "0")}`;
}

function EntryRow({ entry }: { readonly entry: LogEntry }): ReactElement {
  const [open, setOpen] = useState(false);
  const hasFields = Object.keys(entry.fields).length > 0;
  return (
    <li className="px-4 py-2 md:px-5">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1 text-sm md:flex-nowrap">
        <time dateTime={entry.timestamp} className="shrink-0 font-mono text-xs leading-5 text-slate-500 tabular-nums">
          {timeOf(entry.timestamp)}
        </time>
        <span
          className={`shrink-0 rounded px-1.5 text-xs leading-5 font-medium ${levelStyles[isLevel(entry.level) ? entry.level : "DEBUG"]}`}
        >
          {levelLabel(entry.level)}
        </span>
        <div className="order-last min-w-0 flex-1 basis-full md:order-none md:basis-0">
          <p className="font-mono text-xs leading-5 wrap-anywhere whitespace-pre-wrap text-ink">{entry.message}</p>
          <p className="text-xs wrap-anywhere text-slate-500">
            {entry.logger}
            {entry.requestId === null ? null : ` · ${texts.logs.request(entry.requestId)}`}
          </p>
        </div>
        {hasFields ? (
          <button
            type="button"
            aria-expanded={open}
            onClick={() => {
              setOpen(!open);
            }}
            className="ml-auto shrink-0 text-xs text-slate-500 hover:text-ink md:ml-0"
          >
            {open ? texts.logs.hideFields : texts.logs.showFields}
          </button>
        ) : null}
      </div>
      {open ? (
        <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-100 px-4 py-3 font-mono text-xs text-ink">
          {JSON.stringify(entry.fields, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}

type Read = {
  /** Les filtres de la lecture : une réponse d'autres filtres ne s'y ajoute pas. */
  readonly key: string;
  readonly entries: readonly LogEntry[];
  readonly next: string | null;
  readonly at: Date;
};

function keyOf(filters: LogFilters): string {
  return JSON.stringify([filters.service, filters.level, filters.text]);
}

export function LogsTab(): ReactElement {
  const [service, setService] = useState<LogService>("api");
  const [level, setLevel] = useState<LogLevel>("INFO");
  const [typed, setTyped] = useState("");
  // Le texte cherché suit la saisie après une courte pause.
  const [text, setText] = useState("");
  const [read, setRead] = useState<Read | null>(null);
  const [startedAt] = useState(() => new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [failed, setFailed] = useState(false);
  const [live, setLive] = useState(false);
  const [every, setEvery] = useState(5);
  const filters: LogFilters = { service, level, text };
  const key = keyOf(filters);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setText(typed);
    }, 300);
    return () => {
      window.clearTimeout(timer);
    };
  }, [typed]);

  useEffect(() => {
    let current = true;
    const shown: LogFilters = { service, level, text };
    function load(): void {
      readLogs(shown, null).then(
        (page) => {
          if (current) {
            setRead({ key: keyOf(shown), entries: page.entries, next: page.next, at: new Date() });
            setFailed(false);
          }
        },
        () => {
          if (current) {
            setFailed(true);
          }
        },
      );
    }
    load();
    const timer = live ? window.setInterval(load, every * 1000) : undefined;
    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [service, level, text, live, every]);

  function refresh(): void {
    setRefreshing(true);
    readLogs(filters, null).then(
      (page) => {
        setRead({ key, entries: page.entries, next: page.next, at: new Date() });
        setFailed(false);
        setRefreshing(false);
      },
      () => {
        setFailed(true);
        setRefreshing(false);
      },
    );
  }

  function older(): void {
    const before = read?.next ?? null;
    if (before === null) {
      return;
    }
    // Le temps réel relirait la première page : il s'arrête quand on remonte.
    setLive(false);
    setLoadingOlder(true);
    readLogs(filters, before).then(
      (page) => {
        setRead((shown) =>
          shown?.key === key ? { ...shown, entries: [...shown.entries, ...page.entries], next: page.next } : shown,
        );
        setFailed(false);
        setLoadingOlder(false);
      },
      () => {
        setFailed(true);
        setLoadingOlder(false);
      },
    );
  }

  const entries = read?.key === key ? read.entries : null;
  const next = read?.key === key ? read.next : null;

  return (
    <div className="space-y-4">
      <Card title={texts.logs.title}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label={texts.logs.service}>
            <select
              value={service}
              onChange={(event) => {
                const value = services.find((option) => option === event.target.value);
                if (value !== undefined) {
                  setService(value);
                }
              }}
              className={input}
            >
              {services.map((option) => (
                <option key={option} value={option}>
                  {texts.logs.services[option]}
                </option>
              ))}
            </select>
          </Field>
          <Field label={texts.logs.level}>
            <select
              value={level}
              onChange={(event) => {
                if (isLevel(event.target.value)) {
                  setLevel(event.target.value);
                }
              }}
              className={input}
            >
              {levels.map((option) => (
                <option key={option} value={option}>
                  {texts.logs.levels[option]}
                </option>
              ))}
            </select>
          </Field>
          <Field label={texts.logs.text}>
            <input
              type="search"
              value={typed}
              maxLength={200}
              onChange={(event) => {
                setTyped(event.target.value);
              }}
              placeholder={texts.logs.textPlaceholder}
              className={input}
            />
          </Field>
        </div>
        <RefreshBar
          updatedAt={read?.at ?? startedAt}
          refreshing={refreshing}
          onRefresh={refresh}
          live={{ on: live, every, onToggle: setLive, onEvery: setEvery }}
        />
        <div className="-mx-4 -mb-4 border-t border-slate-200 md:-mx-5">
          {entries === null && !failed ? (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          ) : null}
          {entries !== null && entries.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-slate-500 md:px-5">{texts.logs.empty}</p>
          ) : null}
          {entries !== null && entries.length > 0 ? (
            <ul className="divide-y divide-slate-200">
              {entries.map((entry, index) => (
                // Deux entrées peuvent tout partager : la position les distingue.
                <EntryRow key={`${entry.timestamp}-${String(index)}`} entry={entry} />
              ))}
            </ul>
          ) : null}
          {failed ? <p className="px-4 py-3 text-sm text-rose-700 md:px-5">{texts.logs.failed}</p> : null}
          {next === null ? null : (
            <div className="flex justify-center border-t border-slate-200 px-5 py-3">
              <button
                type="button"
                disabled={loadingOlder}
                onClick={older}
                className="flex items-center gap-2 rounded-lg border border-slate-200 bg-surface px-4 py-1.5 text-sm text-ink hover:bg-slate-100 disabled:cursor-wait disabled:opacity-80"
              >
                {loadingOlder ? <Spinner className="size-3.5" /> : null}
                {loadingOlder ? texts.logs.loading : texts.logs.older}
              </button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
