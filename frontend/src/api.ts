const TOKEN_KEY = "chinois.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event("auth-changed"));
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Serveur injoignable. Vérifie ta connexion (VPN ou Tailscale).");
  }
  if (response.status === 401 && path !== "/api/auth/login") {
    setToken(null);
    throw new ApiError(401, "Session expirée. Reconnecte-toi.");
  }
  if (!response.ok) {
    let detail = `Erreur ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    throw new ApiError(response.status, detail);
  }
  return response;
}

export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await request(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  return response.json() as Promise<T>;
}

export async function apiBlob(path: string): Promise<Blob> {
  return (await request(path)).blob();
}

export const errorMessage = (error: unknown) => (error instanceof Error ? error.message : "Erreur inattendue");
