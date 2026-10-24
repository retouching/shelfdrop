// Compte interne, depuis Paramètres › Accès : lecture, création, changement du mot de passe.
import { request } from "./http";

export type InternalAccount = {
  readonly username: string;
  /** Secondes Unix. */
  readonly created_at: number;
  readonly password_changed_at: number;
};

export async function readAccount(): Promise<InternalAccount | null> {
  return (await request<{ readonly account: InternalAccount | null }>("GET", "/v1/account")).account;
}

export function createAccount(username: string, password: string): Promise<InternalAccount> {
  return request<InternalAccount>("POST", "/v1/account", { username, password });
}

export function changePassword(current: string, next: string): Promise<InternalAccount> {
  return request<InternalAccount>("PUT", "/v1/account/password", { current, new: next });
}
