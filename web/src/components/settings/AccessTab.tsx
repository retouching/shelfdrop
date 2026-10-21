// Rubrique API et MCP : jetons d'accès lus, créés (secret affiché une seule fois) et révoqués par
// l'API, configuration MCP et lien vers la documentation OpenAPI.
import { useEffect, useRef, useState, type ReactElement } from "react";

import { ApiError } from "../../api/http";
import { createToken, readTokens, revokeToken, type AccessToken, type Scope } from "../../api/tokens";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { Card, Field, input } from "./parts";

type Expiry = "d30" | "d90" | "d365" | "never";

const expiryDays: Readonly<Record<Expiry, 30 | 90 | 365 | null>> = { d30: 30, d90: 90, d365: 365, never: null };

/** « 21/10 à 18:42 » : la dernière utilisation d'un jeton (secondes Unix). */
function usedAt(seconds: number): string {
  const date = new Date(seconds * 1000);
  return texts.settings.usedAt(
    date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }),
    date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
  );
}

function dayOf(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString("fr-FR");
}

const mcpTools: readonly string[] = [
  "search_works",
  "search_releases",
  "grab_releases",
  "list_downloads",
  "retry_download",
  "list_files_to_place",
  "place_file",
];

const origin = window.location.origin;

const mcpConfig = `{
  "mcpServers": {
    "shelfdrop": {
      "type": "http",
      "url": "${origin}/mcp",
      "headers": { "Authorization": "Bearer <jeton>" }
    }
  }
}`;

function CopyButton({ value }: { readonly value: string }): ReactElement {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
        });
      }}
      className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-ink hover:bg-slate-100"
    >
      {copied ? texts.settings.copied : texts.settings.copy}
    </button>
  );
}

function CreateTokenDialog({
  onClose,
  onCreate,
}: {
  readonly onClose: () => void;
  readonly onCreate: (token: AccessToken) => void;
}): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [scope, setScope] = useState<Scope>("read");
  const [expiry, setExpiry] = useState<Expiry>("d90");
  const [secret, setSecret] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  function create(): void {
    setBusy(true);
    setFailed(false);
    createToken(name.trim(), scope, expiryDays[expiry]).then(
      (created) => {
        setSecret(created.secret);
        onCreate(created.token);
        setBusy(false);
      },
      () => {
        setFailed(true);
        setBusy(false);
      },
    );
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="token-title"
      className="m-auto w-full max-w-lg rounded-2xl border border-slate-200 bg-surface p-0 text-ink shadow-2xl"
    >
      <div className="border-b border-slate-200 px-6 py-4">
        <h2 id="token-title" className="text-lg font-semibold">
          {secret === null ? texts.settings.createTitle : texts.settings.createdTitle}
        </h2>
      </div>
      {secret === null ? (
        <div className="space-y-4 px-6 py-5">
          <Field label={texts.settings.tokenName}>
            <input
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
              placeholder={texts.settings.tokenNamePlaceholder}
              maxLength={100}
              className={input}
            />
          </Field>
          <Field label={texts.settings.tokenScope}>
            <select
              value={scope}
              onChange={(event) => {
                setScope(event.target.value === "write" ? "write" : "read");
              }}
              className={input}
            >
              <option value="read">{texts.settings.scopes.read}</option>
              <option value="write">{texts.settings.scopes.write}</option>
            </select>
          </Field>
          <Field label={texts.settings.expiry}>
            <select
              value={expiry}
              onChange={(event) => {
                const value = event.target.value;
                if (value === "d30" || value === "d90" || value === "d365" || value === "never") {
                  setExpiry(value);
                }
              }}
              className={input}
            >
              {(["d30", "d90", "d365", "never"] as const).map((option) => (
                <option key={option} value={option}>
                  {texts.settings.expiries[option]}
                </option>
              ))}
            </select>
          </Field>
          {failed ? <p className="text-sm text-rose-700">{texts.settings.tokensFailed}</p> : null}
        </div>
      ) : (
        <div className="space-y-3 px-6 py-5">
          <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">{texts.settings.createdHint}</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded-lg bg-slate-100 px-3 py-2 font-mono text-xs text-ink">
              {secret}
            </code>
            <CopyButton value={secret} />
          </div>
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
        {secret === null ? (
          <>
            <button
              type="button"
              onClick={() => {
                ref.current?.close();
              }}
              className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              {texts.settings.cancel}
            </button>
            <button
              type="button"
              onClick={create}
              disabled={busy || name.trim() === ""}
              className="rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-50"
            >
              {texts.settings.create}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => {
              ref.current?.close();
            }}
            className="rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong"
          >
            {texts.settings.close}
          </button>
        )}
      </div>
    </dialog>
  );
}

export function AccessTab(): ReactElement {
  const [tokens, setTokens] = useState<readonly AccessToken[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    readTokens().then(setTokens, () => {
      setFailed(true);
    });
  }, []);

  function revoke(token: AccessToken): void {
    setFailed(false);
    revokeToken(token.id).then(
      () => {
        setTokens((current) => (current ?? []).filter((item) => item.id !== token.id));
      },
      (error: unknown) => {
        if (error instanceof ApiError && error.code === "token_not_found") {
          setTokens((current) => (current ?? []).filter((item) => item.id !== token.id));
          return;
        }
        setFailed(true);
      },
    );
  }

  return (
    <div className="space-y-4">
      <Card
        title={texts.settings.tokens}
        aside={
          <button
            type="button"
            onClick={() => {
              setCreating(true);
            }}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong"
          >
            {texts.settings.newToken}
          </button>
        }
      >
        <table className="-mx-5 -my-4 w-[calc(100%+2.5rem)] text-sm">
          <thead className="bg-band text-left text-ink">
            <tr>
              <th scope="col" className="px-5 py-2.5 font-semibold">
                {texts.settings.tokenName}
              </th>
              <th scope="col" className="px-3 py-2.5 font-semibold">
                {texts.settings.tokenScope}
              </th>
              <th scope="col" className="px-3 py-2.5 font-semibold">
                {texts.settings.tokenLastUsed}
              </th>
              <th scope="col" className="px-3 py-2.5 font-semibold">
                {texts.settings.tokenExpires}
              </th>
              <th scope="col" className="px-5 py-2.5">
                <span className="sr-only">{texts.settings.revoke}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {(tokens ?? []).map((token) => (
              <tr key={token.id}>
                <td className="px-5 py-3 font-medium text-ink">{token.name}</td>
                <td className="px-3 py-3 text-slate-600">{texts.settings.scopes[token.scope]}</td>
                <td className="px-3 py-3 text-slate-600">
                  {token.lastUsedAt === null ? texts.settings.never : usedAt(token.lastUsedAt)}
                </td>
                <td className="px-3 py-3 text-slate-600">
                  {token.expiresAt === null ? texts.settings.never : dayOf(token.expiresAt)}
                </td>
                <td className="px-5 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => {
                      revoke(token);
                    }}
                    aria-label={texts.settings.revokeFor(token.name)}
                    className="text-sm text-slate-500 hover:text-rose-700"
                  >
                    {texts.settings.revoke}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tokens === null && !failed ? <Spinner /> : null}
        {failed ? <p className="text-sm text-rose-700">{texts.settings.tokensFailed}</p> : null}
      </Card>

      <Card title={texts.settings.mcp} aside={<CopyButton value={mcpConfig} />}>
        <pre className="overflow-x-auto rounded-lg bg-slate-100 px-4 py-3 font-mono text-xs text-ink">{mcpConfig}</pre>
        <div>
          <p className="text-sm font-medium text-ink">{texts.settings.mcpTools}</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {mcpTools.map((tool) => (
              <li key={tool} className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">
                {tool}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card title={texts.settings.api}>
        <p className="text-sm text-slate-600">
          {texts.settings.apiLead}{" "}
          <a href="/api/docs" className="font-mono text-xs text-accent-text hover:underline">
            {`${origin}/api/docs`}
          </a>
        </p>
      </Card>

      {creating ? (
        <CreateTokenDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreate={(token) => {
            setTokens((current) => [token, ...(current ?? [])]);
          }}
        />
      ) : null}
    </div>
  );
}
