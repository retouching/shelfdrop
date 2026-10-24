// Installation du premier lancement : le compte interne, puis Prowlarr, qBittorrent, Jellyfin
// (requis), les bibliothèques et le dossier des envois. Chaque étape enregistre ses paramètres :
// on peut revenir en arrière, et une installation reprise repart de la première étape à faire.
import { useEffect, useState, type ReactElement, type SubmitEvent } from "react";

import { ApiError } from "../api/http";
import type { SessionAccount } from "../api/session";
import { testConnection, type SettingValue } from "../api/settings";
import { createSetupAccount, finishSetup } from "../api/setup";
import { loadSettings, saveChangedSettings, useSettings, valueOf } from "../state/settings";
import { texts } from "../texts";
import { AccountFields, draftReady, emptyDraft, type AccountDraft } from "./AccountFields";
import { ShelfIcon } from "./icons";
import { probeMessage } from "./settings/parts";
import { LibrariesCard, ServiceCard, useServiceTests } from "./settings/tabs";
import { Spinner } from "./Skeletons";

const steps = ["account", "prowlarr", "qbittorrent", "jellyfin", "libraries", "finish"] as const;

type Step = (typeof steps)[number];

const primary =
  "flex items-center justify-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-80";
const secondary = "rounded-lg border border-slate-200 px-4 py-2 text-sm text-ink hover:bg-slate-100";

type Props = {
  /** Le compte de la session ; null : le compte interne reste à créer. */
  readonly account: SessionAccount | null;
  readonly onSignedIn: (account: SessionAccount) => void;
  readonly onFinished: () => void;
};

/** La première étape à faire, d'après les paramètres déjà enregistrés. */
function firstStep(saved: (key: string) => SettingValue | undefined): Step {
  if (typeof saved("prowlarr.url") !== "string") {
    return "prowlarr";
  }
  if (typeof saved("qbittorrent.url") !== "string") {
    return "qbittorrent";
  }
  if (typeof saved("jellyfin.url") !== "string") {
    return "jellyfin";
  }
  return "libraries";
}

function AccountStep({ onSignedIn }: { readonly onSignedIn: (account: SessionAccount) => void }): ReactElement {
  const [draft, setDraft] = useState<AccountDraft>(emptyDraft);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(): Promise<void> {
    setPending(true);
    setError(null);
    try {
      onSignedIn(await createSetupAccount(draft.username.trim(), draft.password));
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.code === "account_exists"
          ? texts.setup.accountTaken
          : texts.setup.accountFailed,
      );
      setPending(false);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void send();
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <AccountFields draft={draft} onChange={setDraft} />
      {error === null ? null : (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button type="submit" disabled={pending || !draftReady(draft)} className={primary}>
          {pending ? <Spinner /> : null}
          {pending ? texts.setup.creating : texts.setup.create}
        </button>
      </div>
    </form>
  );
}

function Configure({
  account,
  onFinished,
}: {
  readonly account: SessionAccount;
  readonly onFinished: () => void;
}): ReactElement {
  const settings = useSettings();
  const tests = useServiceTests();
  const [step, setStep] = useState<Step | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSettings().then(
      () => undefined,
      () => {
        setStep("prowlarr");
      },
    );
  }, []);

  // La première étape à faire, une fois les paramètres lus.
  const current: Step | null = step ?? (settings.saved === null ? null : firstStep((key) => valueOf(settings, key)));
  if (current === null) {
    return <Spinner />;
  }
  const index = steps.indexOf(current);

  function go(next: Step): void {
    setError(null);
    setStep(next);
  }

  async function next(): Promise<void> {
    if (current === null) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await saveChangedSettings();
      if (current === "jellyfin") {
        const probe = await testConnection({ service: "jellyfin", url: null, secret: null });
        if (!probe.ok) {
          setError(probeMessage(probe, "Jellyfin").message);
          return;
        }
      }
      setStep(steps[index + 1] ?? "finish");
    } catch {
      setError(texts.setup.saveFailed);
    } finally {
      setPending(false);
    }
  }

  async function finish(): Promise<void> {
    setPending(true);
    setError(null);
    try {
      await finishSetup();
      onFinished();
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.code === "jellyfin_not_connected"
          ? texts.setup.notConnected
          : texts.setup.finishFailed,
      );
      setPending(false);
    }
  }

  return (
    <div className="space-y-5">
      <ol className="flex flex-wrap gap-1.5" aria-label={texts.setup.stepsLabel}>
        {steps.map((option, position) => (
          <li key={option}>
            <button
              type="button"
              disabled={option === "account" || position > index}
              aria-current={option === current ? "step" : undefined}
              onClick={() => {
                go(option);
              }}
              className={
                option === current
                  ? "rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white"
                  : position < index
                    ? "rounded-md bg-slate-100 px-2.5 py-1 text-xs text-ink hover:bg-slate-200"
                    : "rounded-md px-2.5 py-1 text-xs text-slate-400"
              }
            >
              {`${String(position + 1)}. ${texts.setup.steps[option]}`}
            </button>
          </li>
        ))}
      </ol>

      {current === "account" ? (
        <p className="text-sm text-slate-600">{texts.setup.accountDone(account.username)}</p>
      ) : null}
      {current === "prowlarr" || current === "qbittorrent" || current === "jellyfin" ? (
        <ServiceCard id={current} test={tests[current]} />
      ) : null}
      {current === "jellyfin" ? <p className="text-sm text-slate-500">{texts.setup.jellyfinRequired}</p> : null}
      {current === "libraries" ? <LibrariesCard /> : null}
      {current === "finish" ? <p className="text-sm text-slate-600">{texts.setup.finishLead}</p> : null}

      {error === null ? null : (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      )}
      {/* Sur un petit écran, les boutons restent en bas de l'écran pendant que les étapes défilent. */}
      <div className="sticky bottom-0 -mx-4 flex justify-between gap-3 border-t border-slate-200 bg-surface px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:static md:mx-0 md:border-0 md:p-0">
        <button
          type="button"
          disabled={index <= 1}
          onClick={() => {
            go(steps[index - 1] ?? "prowlarr");
          }}
          className={`${secondary} disabled:invisible`}
        >
          {texts.setup.previous}
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            void (current === "finish" ? finish() : next());
          }}
          className={primary}
        >
          {pending ? <Spinner /> : null}
          {current === "finish" ? texts.setup.finish : texts.setup.next}
        </button>
      </div>
    </div>
  );
}

export function SetupPanel({ account, onSignedIn, onFinished }: Props): ReactElement {
  return (
    <main className="flex min-h-dvh items-start justify-center bg-surface md:bg-band md:px-4 md:py-12">
      <div className="w-full space-y-6 bg-surface px-4 pt-8 pb-8 md:max-w-2xl md:rounded-2xl md:border md:border-slate-200 md:p-8 md:shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-white">
            <ShelfIcon className="size-5" />
          </span>
          <span>
            <span className="block text-lg leading-tight font-semibold text-ink">{texts.appName}</span>
            <span className="block text-sm text-slate-500">{texts.appTagline}</span>
          </span>
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink">{texts.setup.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{account === null ? texts.setup.accountLead : texts.setup.lead}</p>
        </div>
        {account === null ? (
          <AccountStep onSignedIn={onSignedIn} />
        ) : (
          <Configure account={account} onFinished={onFinished} />
        )}
      </div>
    </main>
  );
}
