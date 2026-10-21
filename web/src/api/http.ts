// Les appels à l'API de shelfdrop : JSON, erreurs au format {code, detail, data}.

/** Une réponse d'erreur de l'API : `code` est stable, c'est sur lui que la page décide. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isErrorBody(body: unknown): body is { readonly code: string; readonly detail: string } {
  return typeof body === "object" && body !== null && "code" in body && "detail" in body;
}

let onSignedOut: (() => void) | null = null;

/** Appelé quand l'API répond qu'il n'y a plus de session : la page revient à la connexion. */
export function whenSignedOut(handler: (() => void) | null): void {
  onSignedOut = handler;
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    init.headers = { Accept: "application/json", "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, init);
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && isErrorBody(data) && data.code === "not_signed_in") {
      onSignedOut?.();
    }
    throw isErrorBody(data)
      ? new ApiError(response.status, data.code, data.detail)
      : new ApiError(response.status, "http_error", response.statusText);
  }
  return data as T;
}
