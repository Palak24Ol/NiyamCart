export type AuthUser = {
  id: string;
  name: string;
  email: string;
  created_at: string;
};

type AuthResponse = { user: AuthUser };
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const OWNER_KEY = "niyamcart-customer-id";

const rememberUser = (response: AuthResponse) => {
  if (typeof window !== "undefined") window.localStorage.setItem(OWNER_KEY, response.user.id);
  return response;
};

async function authApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || "Authentication could not be completed.");
  return body as T;
}

export const signup = (name: string, email: string, password: string) =>
  authApi<AuthResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  }).then(rememberUser);

export const login = (email: string, password: string) =>
  authApi<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }).then(rememberUser);

export const getCurrentUser = () => authApi<AuthResponse>("/api/auth/me").then(rememberUser);

export const logout = () => authApi<{ status: string }>("/api/auth/logout", { method: "POST" })
  .finally(() => {
    if (typeof window !== "undefined") window.localStorage.removeItem(OWNER_KEY);
  });
