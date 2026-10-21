// Session : connexion avec un compte administrateur de Jellyfin, lecture, déconnexion.
import { ApiError, request } from "./http";

type SessionRead = { readonly username: string };

/** Le compte de la session, ou null sans session. */
export async function readSession(): Promise<string | null> {
  try {
    return (await request<SessionRead>("GET", "/v1/session")).username;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export async function signIn(username: string, password: string): Promise<string> {
  return (await request<SessionRead>("POST", "/v1/session", { username, password })).username;
}

export async function signOut(): Promise<void> {
  await request<null>("DELETE", "/v1/session");
}
