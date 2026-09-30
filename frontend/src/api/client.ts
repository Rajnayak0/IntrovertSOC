export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let csrfToken: string | null = null;

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const res = await fetch('/api/auth/csrf/', { credentials: 'same-origin' });
  const data = await res.json();
  csrfToken = data.csrfToken as string;
  return csrfToken;
}

export function clearCsrf(): void {
  csrfToken = null;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
  retryOnCsrf = true,
): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRFToken'] = await ensureCsrf();
  }

  const res = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    const detail =
      (data && typeof data === 'object' && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : null) ?? `Request failed (${res.status})`;
    if (res.status === 403 && retryOnCsrf && /csrf/i.test(detail)) {
      clearCsrf();
      return api<T>(path, options, false);
    }
    if (res.status === 403 && /credentials/i.test(detail)) {
      throw new ApiError(401, 'Not authenticated');
    }
    throw new ApiError(res.status, detail);
  }
  return data as T;
}
