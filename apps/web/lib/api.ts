// Single switch between LIVE backend and DEMO mode.
// Set NEXT_PUBLIC_API_URL (e.g. https://your-api.onrender.com) to go live.
// Leave it empty and the app runs on demo data with no backend.

import { answerFor, type Source } from "./mock";

const API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export const isLive = () => API.length > 0;

function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("voltaic_token") : null;
}

/** Returns true on success. In demo mode any credentials work. */
export async function login(username: string, password: string): Promise<boolean> {
  if (!isLive()) {
    if (typeof window !== "undefined") localStorage.setItem("voltaic_auth", "1");
    return true;
  }
  try {
    const r = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) return false;
    const d = await r.json();
    localStorage.setItem("voltaic_token", d.access_token);
    localStorage.setItem("voltaic_auth", "1");
    return true;
  } catch {
    return false;
  }
}

export interface KbStats {
  total: number;
  apps: number;
  bySource: { source: string; count: number }[];
}

/** Real knowledge-base stats in live mode; null in demo mode (use mock). */
export async function getStats(): Promise<KbStats | null> {
  if (!isLive()) return null;
  try {
    const r = await fetch(`${API}/api/stats`);
    if (!r.ok) return null;
    const d = await r.json();
    return { total: d.total ?? 0, apps: d.apps ?? 0, bySource: d.bySource ?? [] };
  } catch {
    return null;
  }
}

export interface AskResult {
  answer: string;
  sources: Source[];
}

export async function ask(
  question: string,
  opts: { category?: string; app?: string } = {},
): Promise<AskResult> {
  if (!isLive()) {
    // demo data
    return answerFor(question);
  }
  try {
    const r = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken() ?? ""}`,
      },
      body: JSON.stringify({ question, category: opts.category, app: opts.app }),
    });
    if (r.status === 401) {
      return { answer: "Your session expired. Please sign out and sign in again.", sources: [] };
    }
    if (!r.ok) {
      const detail = await r.json().catch(() => ({}));
      return {
        answer: `The backend returned an error${detail?.detail ? `: ${detail.detail}` : "."}`,
        sources: [],
      };
    }
    const d = await r.json();
    return { answer: d.answer ?? "", sources: (d.sources ?? []) as Source[] };
  } catch (e) {
    return { answer: `Couldn't reach the backend. Is NEXT_PUBLIC_API_URL correct and the API running? (${e})`, sources: [] };
  }
}
