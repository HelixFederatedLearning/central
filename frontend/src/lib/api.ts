// frontend/src/lib/api.ts

const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000/v1";

export type SettingsResp = {
  window_minutes: number;
};

export type RoundRow = {
  id: string;
  status: string;
  created_at: string;
  closed_at: string | null;
  // aliases + optional counts (depending on backend)
  window_start?: string;
  window_end?: string;
  num_hospital?: number | null;
  num_patient?: number | null;
};

export type CurrentModelResp = {
  id: string;
  version: string;
  artifact_url?: string;
};

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`GET ${url} -> ${res.status} ${res.statusText} ${txt}`);
  }
  return res.json() as Promise<T>;
}

export async function getSettings(): Promise<SettingsResp> {
  return getJSON<SettingsResp>(`${API_BASE}/settings`);
}

export async function listRounds(): Promise<RoundRow[]> {
  return getJSON<RoundRow[]>(`${API_BASE}/rounds`);
}

export async function getCurrentModel(): Promise<CurrentModelResp | null> {
  try {
    return await getJSON<CurrentModelResp>(`${API_BASE}/models/current`);
  } catch (e) {
    console.warn("[api] getCurrentModel failed:", e);
    return null;
  }
}

/**
 * Open a Server-Sent Events connection to /v1/events.
 * FedEventsProvider will pass a handler that does JSON.parse(ev.data).
 */
export function openEventsStream(
  onMessage: (ev: MessageEvent) => void
): EventSource {
  const url = `${API_BASE}/events`; // -> e.g. http://localhost:8000/v1/events
  const es = new EventSource(url);

  es.onmessage = onMessage;
  es.onerror = (err) => {
    console.warn("[api] SSE error:", err);
  };

  return es;
}
