// Identifiant, mot de passe et sa confirmation : la création du compte interne (installation,
// Paramètres › Accès).
import type { ReactElement } from "react";

import { texts } from "../texts";
import { Field, input } from "./settings/parts";

/** Longueur minimale d'un mot de passe du compte interne (celle de l'API). */
export const PASSWORD_MIN = 10;

export type AccountDraft = { readonly username: string; readonly password: string; readonly confirm: string };

export const emptyDraft: AccountDraft = { username: "", password: "", confirm: "" };

/** Le brouillon envoyable : un identifiant, un mot de passe assez long, confirmé. */
export function draftReady(draft: AccountDraft): boolean {
  return draft.username.trim() !== "" && draft.password.length >= PASSWORD_MIN && draft.password === draft.confirm;
}

export function AccountFields({
  draft,
  onChange,
}: {
  readonly draft: AccountDraft;
  readonly onChange: (draft: AccountDraft) => void;
}): ReactElement {
  const mismatch = draft.confirm !== "" && draft.password !== draft.confirm;
  return (
    <div className="space-y-4">
      <Field label={texts.login.username}>
        <input
          value={draft.username}
          onChange={(event) => {
            onChange({ ...draft, username: event.target.value });
          }}
          autoComplete="username"
          maxLength={64}
          required
          className={input}
        />
      </Field>
      <Field label={texts.login.password} hint={texts.account.passwordHint}>
        <input
          type="password"
          value={draft.password}
          onChange={(event) => {
            onChange({ ...draft, password: event.target.value });
          }}
          autoComplete="new-password"
          minLength={PASSWORD_MIN}
          required
          className={input}
        />
      </Field>
      <Field label={texts.account.confirm}>
        <input
          type="password"
          value={draft.confirm}
          onChange={(event) => {
            onChange({ ...draft, confirm: event.target.value });
          }}
          autoComplete="new-password"
          required
          className={input}
        />
      </Field>
      {mismatch ? <p className="text-sm text-rose-700">{texts.account.mismatch}</p> : null}
    </div>
  );
}
