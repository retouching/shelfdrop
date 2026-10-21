// Les jetons d'accès de l'API et du serveur MCP : lus, créés (le secret n'arrive qu'une fois), révoqués.
import { request } from "./http";

export type Scope = "read" | "write";

export type AccessToken = {
  readonly id: number;
  readonly name: string;
  readonly scope: Scope;
  /** Secondes Unix. */
  readonly createdAt: number;
  readonly expiresAt: number | null;
  readonly lastUsedAt: number | null;
};

type TokenRead = {
  readonly id: number;
  readonly name: string;
  readonly scope: Scope;
  readonly created_by: string;
  readonly created_at: number;
  readonly expires_at: number | null;
  readonly last_used_at: number | null;
};

function tokenOf(read: TokenRead): AccessToken {
  return {
    id: read.id,
    name: read.name,
    scope: read.scope,
    createdAt: read.created_at,
    expiresAt: read.expires_at,
    lastUsedAt: read.last_used_at,
  };
}

export async function readTokens(): Promise<readonly AccessToken[]> {
  const body = await request<{ readonly tokens: readonly TokenRead[] }>("GET", "/v1/tokens");
  return body.tokens.map(tokenOf);
}

/** Le jeton créé et son secret, affiché une seule fois. */
export async function createToken(
  name: string,
  scope: Scope,
  days: 30 | 90 | 365 | null,
): Promise<{ readonly token: AccessToken; readonly secret: string }> {
  const body = await request<{ readonly token: TokenRead; readonly secret: string }>("POST", "/v1/tokens", {
    name,
    scope,
    days,
  });
  return { token: tokenOf(body.token), secret: body.secret };
}

export async function revokeToken(id: number): Promise<void> {
  await request<null>("DELETE", `/v1/tokens/${String(id)}`);
}
