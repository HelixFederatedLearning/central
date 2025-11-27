// src/lib/api.ts
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API = `${BASE_URL}/v1`;

export function getToken(): string | null {
  return localStorage.getItem("token");
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function getSettings() {
  const res = await fetch(`${API}/settings`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listRounds() {
  const res = await fetch(`${API}/rounds`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getCurrentModel() {
  const res = await fetch(`${API}/models/current`, { headers: { ...authHeaders() } });
  if (res.status === 404) return null; // no current model yet
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function openEventsStream(onEvent: (e: MessageEvent) => void): EventSource {
  // SSE does not support Authorization header, so append token via query param (backend should allow it)
  const t = getToken();
  const url = new URL(`${API}/events`);
  if (t) url.searchParams.set("token", t);
  const es = new EventSource(url.toString(), { withCredentials: false });
  es.onmessage = onEvent;
  return es;
}
