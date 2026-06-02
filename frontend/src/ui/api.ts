export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type Conversation = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
};

function getSessionId(): string {
  const key = "ollive_session_id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const v = crypto.randomUUID();
  localStorage.setItem(key, v);
  return v;
}

export async function createConversation(title?: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE_URL}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title || null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE_URL}/api/conversations`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listMessages(conversationId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function cancelConversation(conversationId: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

type SSEEvent =
  | { type: "meta"; inference_id: string; trace_id: string }
  | { type: "delta"; text: string }
  | { type: "done"; status: "success" | "error" | "cancelled"; message_id?: string; error?: string };

export async function streamChat(
  conversationId: string,
  content: string,
  onEvent: (evt: SSEEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": getSessionId(),
    },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await res.text());

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = raw
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      const jsonStr = line.replace(/^data:\s*/, "");
      try {
        onEvent(JSON.parse(jsonStr));
      } catch {
        // ignore malformed events
      }
    }
  }
}

export async function getMetricsSummary(): Promise<{
  total_inferences: number;
  success: number;
  error: number;
  cancelled: number;
  avg_latency_ms: number | null;
}> {
  const res = await fetch(`${API_BASE_URL}/api/metrics/summary`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRecentInferences(): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/api/metrics/recent`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

