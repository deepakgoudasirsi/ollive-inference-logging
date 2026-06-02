import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  cancelConversation,
  createConversation,
  getMetricsSummary,
  getRecentInferences,
  listConversations,
  listMessages,
  streamChat,
  type Conversation,
  type Message,
} from "./api";

type Tab = "chat" | "metrics";

export function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const active = useMemo(() => convos.find((c) => c.id === activeId) || null, [convos, activeId]);

  async function refreshConvos(selectId?: string) {
    const items = await listConversations();
    setConvos(items);
    if (selectId) setActiveId(selectId);
    if (!activeId && items[0]) setActiveId(items[0].id);
  }

  async function refreshMessages(conversationId: string) {
    setMessages(await listMessages(conversationId));
  }

  useEffect(() => {
    refreshConvos().catch(console.error);
  }, []);

  useEffect(() => {
    if (!activeId) return;
    refreshMessages(activeId).catch(console.error);
  }, [activeId]);

  async function onNewConversation() {
    const c = await createConversation();
    await refreshConvos(c.id);
    await refreshMessages(c.id);
    setTab("chat");
  }

  async function onCancelConversation() {
    if (!activeId) return;
    abortRef.current?.abort();
    setStreaming(false);
    const updated = await cancelConversation(activeId);
    setConvos((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  async function onSend() {
    if (!activeId) return;
    const text = draft.trim();
    if (!text) return;
    if (active?.status !== "active") return;

    setDraft("");
    setStreaming(true);
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    // optimistic user bubble (backend also stores it)
    const tempUser: Message = {
      id: crypto.randomUUID(),
      conversation_id: activeId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    const tempAsstId = crypto.randomUUID();
    const tempAsst: Message = {
      id: tempAsstId,
      conversation_id: activeId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, tempUser, tempAsst]);

    try {
      await streamChat(
        activeId,
        text,
        (evt) => {
          if (evt.type === "delta") {
            setMessages((prev) =>
              prev.map((m) => (m.id === tempAsstId ? { ...m, content: m.content + evt.text } : m)),
            );
          } else if (evt.type === "done") {
            setStreaming(false);
            refreshConvos().catch(() => {});
            refreshMessages(activeId).catch(() => {});
          }
        },
        ac.signal,
      );
    } catch (e) {
      setStreaming(false);
      setMessages((prev) =>
        prev.map((m) => (m.id === tempAsstId ? { ...m, content: `(error) ${String(e)}` } : m)),
      );
    }
  }

  const [summary, setSummary] = useState<any>(null);
  const [recent, setRecent] = useState<any[]>([]);

  async function refreshMetrics() {
    const [s, r] = await Promise.all([getMetricsSummary(), getRecentInferences()]);
    setSummary(s);
    setRecent(r);
  }

  useEffect(() => {
    if (tab !== "metrics") return;
    refreshMetrics().catch(console.error);
    const t = setInterval(() => refreshMetrics().catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [tab]);

  return (
    <div className="layout">
      <div className="sidebar">
        <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontWeight: 700 }}>Ollive</div>
          <button className="btn btnPrimary" onClick={onNewConversation}>
            New
          </button>
        </div>
        <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          Conversations
        </div>
        <div className="convoList">
          {convos.map((c) => (
            <div
              key={c.id}
              className={`convoItem ${activeId === c.id ? "convoItemActive" : ""}`}
              onClick={() => {
                abortRef.current?.abort();
                setStreaming(false);
                setActiveId(c.id);
                setTab("chat");
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.title || "Conversation"}
                </div>
                <div className="pill">{c.status}</div>
              </div>
              <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                updated {new Date(c.updated_at).toLocaleString()}
              </div>
            </div>
          ))}
          {convos.length === 0 && <div className="muted">No conversations yet.</div>}
        </div>
      </div>

      <div className="main">
        <div className="topbar">
          <div className="tabs">
            <button className={`btn ${tab === "chat" ? "btnPrimary" : ""}`} onClick={() => setTab("chat")}>
              Chat
            </button>
            <button className={`btn ${tab === "metrics" ? "btnPrimary" : ""}`} onClick={() => setTab("metrics")}>
              Metrics
            </button>
          </div>
          <div className="pill">provider={import.meta.env.VITE_PROVIDER || "server-configured"}</div>
          <div style={{ flex: 1 }} />
          <button className="btn btnDanger" disabled={!activeId} onClick={onCancelConversation}>
            Cancel conversation
          </button>
        </div>

        {tab === "chat" ? (
          <>
            <div className="chat">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`bubble ${m.role === "user" ? "bubbleUser" : "bubbleAsst"}`}
                  title={new Date(m.created_at).toLocaleString()}
                >
                  <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                    {m.role}
                  </div>
                  {m.content}
                </div>
              ))}
              {!activeId && <div className="muted">Create a conversation to begin.</div>}
            </div>
            <div className="composer">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={active?.status === "cancelled" ? "Conversation cancelled" : "Message…"}
                disabled={!activeId || active?.status !== "active" || streaming}
              />
              <button className="btn btnPrimary" onClick={onSend} disabled={!activeId || streaming}>
                {streaming ? "Streaming…" : "Send"}
              </button>
              <button
                className="btn"
                onClick={() => {
                  abortRef.current?.abort();
                  setStreaming(false);
                }}
                disabled={!streaming}
              >
                Stop
              </button>
            </div>
          </>
        ) : (
          <div className="chat">
            <div className="grid2">
              <div className="card">
                <div className="muted">Total inferences</div>
                <div className="kpi">{summary?.total_inferences ?? "—"}</div>
              </div>
              <div className="card">
                <div className="muted">Avg latency (ms)</div>
                <div className="kpi">{summary?.avg_latency_ms ? Math.round(summary.avg_latency_ms) : "—"}</div>
              </div>
              <div className="card">
                <div className="muted">Success / Error / Cancelled</div>
                <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 14 }}>
                  <div className="tagOk">success: {summary?.success ?? "—"}</div>
                  <div className="tagErr">error: {summary?.error ?? "—"}</div>
                  <div className="muted">cancelled: {summary?.cancelled ?? "—"}</div>
                </div>
              </div>
              <div className="card">
                <div className="muted">Live refresh</div>
                <div style={{ marginTop: 8 }}>Every 2s while this tab is open.</div>
              </div>
            </div>

            <div className="card" style={{ marginTop: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontWeight: 700 }}>Recent inference logs</div>
                <button className="btn" onClick={() => refreshMetrics().catch(() => {})}>
                  Refresh
                </button>
              </div>
              <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                Shows redacted previews (email/phone/card).
              </div>
              <div style={{ overflow: "auto", marginTop: 10 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>started</th>
                      <th>status</th>
                      <th>latency</th>
                      <th>provider/model</th>
                      <th>request preview</th>
                      <th>response preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((r) => (
                      <tr key={r.id}>
                        <td className="muted" style={{ whiteSpace: "nowrap" }}>
                          {new Date(r.started_at).toLocaleTimeString()}
                        </td>
                        <td>
                          {r.status === "success" ? (
                            <span className="tagOk">{r.status}</span>
                          ) : r.status === "error" ? (
                            <span className="tagErr">{r.status}</span>
                          ) : (
                            <span className="muted">{r.status}</span>
                          )}
                          {r.error_type ? <div className="muted">{r.error_type}</div> : null}
                        </td>
                        <td className="muted">{r.latency_ms ?? "—"} ms</td>
                        <td className="muted">
                          {r.provider}/{r.model}
                        </td>
                        <td style={{ minWidth: 260 }}>{r.request_preview ?? "—"}</td>
                        <td style={{ minWidth: 260 }}>{r.response_preview ?? "—"}</td>
                      </tr>
                    ))}
                    {recent.length === 0 && (
                      <tr>
                        <td colSpan={6} className="muted">
                          No logs yet. Send a message in the Chat tab.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

