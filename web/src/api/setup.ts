// Installation du premier lancement : son état, le compte interne (première étape), la fin.
import { request } from "./http";
import type { SessionAccount } from "./session";

export type SetupState = {
  /** L'installation n'est pas finie : l'API ne répond qu'à elle, à la session et aux paramètres. */
  readonly needed: boolean;
  /** Le compte interne existe. */
  readonly account: boolean;
};

export function readSetup(): Promise<SetupState> {
  return request<SetupState>("GET", "/v1/setup");
}

/** Crée le compte interne et ouvre sa session. */
export function createSetupAccount(username: string, password: string): Promise<SessionAccount> {
  return request<SessionAccount>("POST", "/v1/setup/account", { username, password });
}

/** Termine l'installation ; refusée (`jellyfin_not_connected`) tant que Jellyfin ne répond pas. */
export function finishSetup(): Promise<SetupState> {
  return request<SetupState>("POST", "/v1/setup/finish");
}
