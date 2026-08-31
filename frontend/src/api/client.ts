const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = typeof payload.detail === "string" ? payload.detail : undefined;
    } catch {
      detail = undefined;
    }

    throw new ApiError(
      detail ?? `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string, token?: string | null): Promise<T> {
  return apiRequest<T>(path, { method: "GET" }, token);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  token?: string | null,
): Promise<T> {
  return apiRequest<T>(
    path,
    {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    token,
  );
}

export async function apiPut<T>(
  path: string,
  body?: unknown,
  token?: string | null,
): Promise<T> {
  return apiRequest<T>(
    path,
    {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    token,
  );
}

export async function apiDelete(path: string, token?: string | null): Promise<void> {
  return apiRequest<void>(path, { method: "DELETE" }, token);
}

export interface HealthResponse {
  status: string;
  service: string;
}

export async function getHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health");
}
