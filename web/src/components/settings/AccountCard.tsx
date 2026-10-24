// Le compte interne dans Paramètres › Accès : créé s'il n'existe pas (une installation qui se
// connecte par Jellyfin), son mot de passe changé (l'actuel demandé).
import { useEffect, useState, type ReactElement, type SubmitEvent } from "react";

import { changePassword, createAccount, readAccount, type InternalAccount } from "../../api/account";
import { ApiError } from "../../api/http";
import { locale, texts } from "../../texts";
import { AccountFields, draftReady, emptyDraft, PASSWORD_MIN, type AccountDraft } from "../AccountFields";
import { Spinner } from "../Skeletons";
import { Card, Field, input } from "./parts";

const button =
  "flex items-center gap-2 rounded-lg border border-transparent bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-60";

function dayOf(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString(locale);
}

function CreateForm({ onCreated }: { readonly onCreated: (account: InternalAccount) => void }): ReactElement {
  const [draft, setDraft] = useState<AccountDraft>(emptyDraft);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function send(): Promise<void> {
    setPending(true);
    setFailed(false);
    try {
      onCreated(await createAccount(draft.username.trim(), draft.password));
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void send();
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-600">{texts.account.none}</p>
      <AccountFields draft={draft} onChange={setDraft} />
      {failed ? <p className="text-sm text-rose-700">{texts.setup.accountFailed}</p> : null}
      <button type="submit" disabled={pending || !draftReady(draft)} className={button}>
        {pending ? <Spinner className="size-3.5" /> : null}
        {texts.setup.create}
      </button>
    </form>
  );
}

function PasswordForm({ onChanged }: { readonly onChanged: (account: InternalAccount) => void }): ReactElement {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<{ readonly ok: boolean; readonly text: string } | null>(null);

  async function send(): Promise<void> {
    setPending(true);
    setMessage(null);
    try {
      onChanged(await changePassword(current, next));
      setCurrent("");
      setNext("");
      setMessage({ ok: true, text: texts.account.changed });
    } catch (caught) {
      const wrong = caught instanceof ApiError && caught.code === "password_refused";
      setMessage({ ok: false, text: wrong ? texts.account.wrongPassword : texts.account.changeFailed });
    } finally {
      setPending(false);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void send();
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={texts.account.currentPassword}>
          <input
            type="password"
            value={current}
            onChange={(event) => {
              setCurrent(event.target.value);
            }}
            autoComplete="current-password"
            required
            className={input}
          />
        </Field>
        <Field label={texts.account.newPassword} hint={texts.account.passwordHint}>
          <input
            type="password"
            value={next}
            onChange={(event) => {
              setNext(event.target.value);
            }}
            autoComplete="new-password"
            minLength={PASSWORD_MIN}
            required
            className={input}
          />
        </Field>
      </div>
      {message === null ? null : (
        <p role="status" className={`text-sm ${message.ok ? "text-emerald-700" : "text-rose-700"}`}>
          {message.text}
        </p>
      )}
      <button type="submit" disabled={pending || current === "" || next.length < PASSWORD_MIN} className={button}>
        {pending ? <Spinner className="size-3.5" /> : null}
        {texts.account.change}
      </button>
    </form>
  );
}

export function AccountCard(): ReactElement {
  // undefined : pas encore lu ; null : aucun compte interne.
  const [account, setAccount] = useState<InternalAccount | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    readAccount().then(setAccount, () => {
      setFailed(true);
    });
  }, []);

  return (
    <Card title={texts.account.title} hint={texts.account.hint}>
      {failed ? <p className="text-sm text-rose-700">{texts.account.readFailed}</p> : null}
      {account === undefined && !failed ? <Spinner /> : null}
      {account === null ? <CreateForm onCreated={setAccount} /> : null}
      {account === undefined || account === null ? null : (
        <>
          <p className="text-sm text-slate-600">
            <span className="font-medium text-ink">{account.username}</span>
            {" · "}
            {texts.account.changedAt(dayOf(account.password_changed_at))}
          </p>
          <PasswordForm onChanged={setAccount} />
        </>
      )}
    </Card>
  );
}
