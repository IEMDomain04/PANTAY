import type { ChatRequest, ChatResponse, HealthResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function sendChat(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as ChatResponse;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/api/health`, { signal });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as HealthResponse;
}
