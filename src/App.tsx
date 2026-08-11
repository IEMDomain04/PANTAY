import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { getHealth, sendChat } from "./api";
import type { HealthResponse, Message, Source } from "./types";
import "./App.css";

const prompts = [
  "What are the grounds for annulment in the Philippines?",
  "Explain due process in simple terms.",
  "What rights does an employee have after dismissal?",
  "Summarize the legal rules on online defamation.",
];

function Icon({ name, size = 20 }: { name: "menu" | "plus" | "send" | "book" | "scales" | "copy" | "check" | "external" | "trash" | "close"; size?: number }) {
  const paths: Record<typeof name, ReactNode> = {
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></>,
    scales: <><path d="m16 16 3-8 3 8a5 5 0 0 1-6 0ZM2 16l3-8 3 8a5 5 0 0 1-6 0ZM12 3v18M3 7h18M8 21h8" /></>,
    copy: <><rect width="14" height="14" x="8" y="8" rx="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></>,
    check: <><path d="m5 12 4 4L19 6" /></>,
    external: <><path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /></>,
    trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g);
  return <>{parts.map((part, index) => {
    if (/^\*\*.*\*\*$/.test(part)) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (/^`.*`$/.test(part)) return <code key={index}>{part.slice(1, -1)}</code>;
    if (/^\[\d+\]$/.test(part)) return <span className="citation-marker" key={index}>{part}</span>;
    return part;
  })}</>;
}

function AnswerText({ content }: { content: string }) {
  return <div className="answer-text">{content.split("\n").map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return <div className="answer-gap" key={index} />;
    if (/^#{1,3}\s/.test(trimmed)) return <h3 key={index}><InlineText text={trimmed.replace(/^#{1,3}\s/, "")} /></h3>;
    if (/^[-*]\s/.test(trimmed)) return <div className="answer-list" key={index}><span>•</span><p><InlineText text={trimmed.slice(2)} /></p></div>;
    if (/^\d+[.)]\s/.test(trimmed)) return <div className="answer-list" key={index}><span>{trimmed.match(/^\d+/)?.[0]}.</span><p><InlineText text={trimmed.replace(/^\d+[.)]\s/, "")} /></p></div>;
    return <p key={index}><InlineText text={trimmed} /></p>;
  })}</div>;
}

function SourceCard({ source }: { source: Source }) {
  const body = <>
    <div className="source-card-top"><span className="source-number">{source.citation}</span><span className="source-type">Legal source</span>{source.url && <Icon name="external" size={15} />}</div>
    <strong>{source.title}</strong>
    <span className="source-origin">{source.source}</span>
    <p>{source.excerpt}</p>
  </>;
  return source.url ? <a className="source-card" href={source.url} target="_blank" rel="noreferrer">{body}</a> : <div className="source-card">{body}</div>;
}

function AssistantMessage({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };
  return <article className={`assistant-message${message.error ? " error-message" : ""}`}>
    <div className="assistant-avatar"><Icon name="scales" size={18} /></div>
    <div className="message-content">
      <div className="message-heading"><strong>Katwiran</strong><span>Legal research assistant</span></div>
      <AnswerText content={message.content} />
      {!!message.sources?.length && <section className="sources"><h4><Icon name="book" size={17} /> Sources consulted</h4><div className="source-grid">{message.sources.map(source => <SourceCard key={source.chunk_id} source={source} />)}</div></section>}
      {!message.error && <button className="copy-button" onClick={copy}>{copied ? <Icon name="check" size={16} /> : <Icon name="copy" size={16} />}{copied ? "Copied" : "Copy answer"}</button>}
    </div>
  </article>;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [statusError, setStatusError] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const recentTitle = useMemo(() => messages.find(message => message.role === "user")?.content ?? "New legal research", [messages]);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then(setHealth).catch(() => setStatusError(true));
    return () => controller.abort();
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [draft]);

  const newChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setDraft("");
    setLoading(false);
    setSidebarOpen(false);
    textareaRef.current?.focus();
  };

  const submit = async (text = draft) => {
    const cleaned = text.trim();
    if (!cleaned || loading) return;

    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: cleaned, createdAt: new Date().toISOString() };
    const prior = messages.map(({ role, content }) => ({ role, content }));
    setMessages(current => [...current, userMessage]);
    setDraft("");
    setLoading(true);
    abortRef.current = new AbortController();

    try {
      const response = await sendChat({ message: cleaned, history: prior.slice(-8) }, abortRef.current.signal);
      setMessages(current => [...current, {
        id: crypto.randomUUID(), role: "assistant", content: response.answer,
        sources: response.sources, createdAt: new Date().toISOString(),
      }]);
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setMessages(current => [...current, {
          id: crypto.randomUUID(), role: "assistant", error: true,
          content: `I couldn't complete the legal search. ${(error as Error).message}`,
          createdAt: new Date().toISOString(),
        }]);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  };

  const backendReady = health?.rag_ready && health?.gemini_ready;

  return <div className="app-shell">
    {sidebarOpen && <button className="scrim" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar${sidebarOpen ? " open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Icon name="scales" size={22} /></div><div><strong>Katwiran</strong><span>Philippine Legal AI</span></div><button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><Icon name="close" /></button></div>
      <button className="new-chat" onClick={newChat}><Icon name="plus" size={18} /> New conversation</button>
      <div className="sidebar-section"><p>RECENT</p><button className="history-item active"><span>{recentTitle}</span></button></div>
      <div className="sidebar-note"><Icon name="book" size={18} /><div><strong>Research responsibly</strong><span>Verify citations and consult a qualified Philippine lawyer for legal advice.</span></div></div>
      <div className="connection"><span className={`status-dot${backendReady ? " online" : ""}`} /><div><strong>{backendReady ? "Knowledge base ready" : statusError ? "Backend offline" : "Checking knowledge base"}</strong><span>{health?.rag_ready ? "OmniCorpus connected" : "FAISS + Gemini status"}</span></div></div>
    </aside>

    <main className="main-panel">
      <header className="topbar"><button className="menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Icon name="menu" /></button><div className="topbar-title"><span>Philippine law</span><div className="verified-pill"><span /> RAG enabled</div></div><div className="model-pill">Gemini <span>•</span> E5</div></header>

      <div className={`conversation${messages.length === 0 ? " empty" : ""}`}>
        {messages.length === 0 ? <section className="welcome">
          <div className="welcome-mark"><Icon name="scales" size={30} /></div>
          <p className="eyebrow">PHILIPPINE LEGAL RESEARCH</p>
          <h1>What would you like to understand?</h1>
          <p className="welcome-copy">Explore Philippine laws, decisions, and legal concepts with answers grounded in retrieved sources.</p>
          <div className="prompt-grid">{prompts.map(prompt => <button key={prompt} onClick={() => void submit(prompt)}><span>{prompt}</span><Icon name="send" size={16} /></button>)}</div>
        </section> : <div className="messages">{messages.map(message => message.role === "user" ? <article className="user-message" key={message.id}><div>{message.content}</div></article> : <AssistantMessage key={message.id} message={message} />)}{loading && <article className="assistant-message"><div className="assistant-avatar"><Icon name="scales" size={18} /></div><div className="message-content"><div className="message-heading"><strong>Katwiran</strong><span>Searching legal sources</span></div><div className="thinking"><i /><i /><i /><span>Retrieving and reviewing relevant passages…</span></div></div></article>}</div>}
        <div ref={endRef} />
      </div>

      <footer className="composer-area"><div className="composer"><textarea ref={textareaRef} value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={onKeyDown} rows={1} maxLength={4000} placeholder="Ask about Philippine law…" aria-label="Legal question" /><button className="send-button" disabled={!draft.trim() || loading} onClick={() => void submit()} aria-label="Send question"><Icon name="send" size={19} /></button></div><p>Katwiran can make mistakes. Responses are legal information, not legal advice. Verify important details.</p></footer>
    </main>
  </div>;
}

export default App;
