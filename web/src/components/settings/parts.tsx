// Briques communes de la page Paramètres : carte, champs, secret, test de connexion.
import { useState, type ReactElement, type ReactNode } from "react";

import type { ProbeRead } from "../../api/settings";
import { texts } from "../../texts";
import { CheckIcon } from "../icons";
import { Spinner } from "../Skeletons";

export const input =
  "w-full rounded-lg border border-slate-200 bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

export function Card({
  title,
  hint,
  aside,
  children,
}: {
  readonly title: string;
  readonly hint?: string;
  readonly aside?: ReactNode;
  readonly children: ReactNode;
}): ReactElement {
  return (
    <section className="rounded-xl border border-slate-200 bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-4 md:px-5">
        <div className="min-w-0">
          <h2 className="font-semibold text-ink">{title}</h2>
          {hint === undefined ? null : <p className="mt-0.5 text-sm text-slate-500">{hint}</p>}
        </div>
        {aside}
      </header>
      <div className="space-y-4 px-4 py-4 md:px-5">{children}</div>
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  readonly label: string;
  readonly hint?: string;
  readonly children: ReactNode;
}): ReactElement {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
      {hint === undefined ? null : <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  readonly label: string;
  readonly hint?: string;
  readonly checked: boolean;
  readonly onChange: (checked: boolean) => void;
}): ReactElement {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <span>
        <span className="block text-sm font-medium text-ink">{label}</span>
        {hint === undefined ? null : <span className="block text-xs text-slate-500">{hint}</span>}
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
        className="peer sr-only"
      />
      <span
        aria-hidden="true"
        className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-slate-300 transition peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-ring after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white after:transition peer-checked:after:translate-x-4"
      />
    </label>
  );
}

/** « 21/10/2026 » : la date de définition d'un secret (secondes Unix). */
function dayOf(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString("fr-FR");
}

/**
 * Secret : jamais affiché ni renvoyé, seulement sa date. On peut le remplacer ou l'effacer ;
 * `edit` est la modification en cours (une valeur saisie, null : effacé), enregistrée par le
 * bouton « Enregistrer ».
 */
export function SecretField({
  label,
  setAt,
  edit,
  onEdit,
  optional,
}: {
  readonly label: string;
  readonly setAt: number | null;
  readonly edit: string | null | undefined;
  readonly onEdit: (edit: string | null | undefined) => void;
  readonly optional?: boolean;
}): ReactElement {
  const editing = typeof edit === "string";
  const isSet = setAt !== null && edit !== null;

  return (
    <div className="space-y-1.5">
      <span className="block text-sm font-medium text-ink">
        {label}
        {optional === true ? <span className="font-normal text-slate-500"> · {texts.settings.optionalKey}</span> : null}
      </span>
      {editing ? (
        <div className="flex gap-2">
          <input
            type="password"
            autoComplete="off"
            aria-label={label}
            value={edit}
            onChange={(event) => {
              onEdit(event.target.value);
            }}
            className={input}
          />
          <button
            type="button"
            onClick={() => {
              onEdit(undefined);
            }}
            className="rounded-lg px-3 text-sm text-slate-600 hover:bg-slate-100"
          >
            {texts.settings.cancel}
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-300 px-3 py-2">
          <span className={`flex-1 text-sm ${isSet ? "text-ink" : "text-slate-500"}`}>
            {setAt !== null && edit !== null
              ? `•••••••• · ${texts.settings.secretSet(dayOf(setAt))}`
              : texts.settings.secretUnset}
          </span>
          <button
            type="button"
            onClick={() => {
              onEdit("");
            }}
            className="text-sm font-medium text-accent-text hover:underline"
          >
            {texts.settings.replace}
          </button>
          {isSet ? (
            <button
              type="button"
              onClick={() => {
                onEdit(null);
              }}
              className="text-sm text-slate-500 hover:text-rose-700"
            >
              {texts.settings.clear}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

export type TestResult = { readonly ok: boolean; readonly message: string };

export type TestState =
  { readonly kind: "idle" } | { readonly kind: "running" } | ({ readonly kind: "done" } & TestResult);

export type ConnectionTest = { readonly state: TestState; readonly run: () => Promise<void> };

/** « 2.1.5.5216 » → « 2.1 ». */
function shortVersion(version: string | null): string {
  return (version ?? "").split(".").slice(0, 2).join(".");
}

/** Le message d'un test, avec les textes de la page ; `name` : le nom du service. */
export function probeMessage(probe: ProbeRead, name: string): TestResult {
  const results = texts.settings.results;
  switch (probe.state) {
    case "connected": {
      if (probe.elapsed_ms !== null) {
        const seconds = (probe.elapsed_ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 });
        return { ok: true, message: results.answersIn(seconds) };
      }
      const count = probe.count ?? 0;
      const detail =
        probe.service === "prowlarr"
          ? results.indexers(count)
          : probe.service === "torrent"
            ? results.categories(count)
            : results.libraries(count);
      return { ok: true, message: results.connected([`${name} ${shortVersion(probe.version)}`, detail]) };
    }
    case "no_address":
    case "no_key":
      return { ok: false, message: results.keyMissing };
    case "refused":
      return { ok: false, message: results.refused(probe.status ?? 401, name) };
    case "unavailable":
      return { ok: false, message: results.noAnswer(probe.status) };
  }
}

/** Un test de connexion : `probe` l'envoie avec les valeurs saisies. */
export function useConnectionTest(probe: () => Promise<TestResult>): ConnectionTest {
  const [state, setState] = useState<TestState>({ kind: "idle" });
  async function run(): Promise<void> {
    setState({ kind: "running" });
    try {
      setState({ kind: "done", ...(await probe()) });
    } catch {
      setState({ kind: "done", ok: false, message: texts.settings.results.noAnswer(null) });
    }
  }
  return { state, run };
}

export function TestStatus({ state }: { readonly state: TestState }): ReactElement {
  switch (state.kind) {
    case "idle":
      return <span className="text-sm text-slate-500">{texts.settings.untested}</span>;
    case "running":
      return (
        <span className="flex items-center gap-2 text-sm text-slate-600">
          <Spinner className="size-3.5" />
          {texts.settings.testing}
        </span>
      );
    case "done":
      return (
        <span
          role="status"
          className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${
            state.ok ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-rose-50 text-rose-700 ring-rose-200"
          }`}
        >
          {state.ok ? <CheckIcon className="size-3.5" /> : null}
          {state.message}
        </span>
      );
  }
}

export function TestButton({ onClick, busy }: { readonly onClick: () => void; readonly busy: boolean }): ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-ink hover:bg-slate-100 disabled:cursor-wait disabled:opacity-60"
    >
      {texts.settings.test}
    </button>
  );
}
