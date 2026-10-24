// Session : connexion avec le compte interne ou un compte administrateur de Jellyfin, lecture,
// déconnexion.
import { ApiError, request } from "./http";

/** Le compte de la session : `internal`, le compte interne de shelfdrop. */
export type SessionAccount = { readonly username: string; readonly internal: boolean };

/** Le compte de la session, ou null sans session. */
export async function readSession(): Promise<SessionAccount | null> {
  try {
    return await request<SessionAccount>("GET", "/v1/session");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export function signIn(username: string, password: string): Promise<SessionAccount> {
  return request<SessionAccount>("POST", "/v1/session", { username, password });
}

export async function signOut(): Promise<void> {
  await request<null>("DELETE", "/v1/session");
}
