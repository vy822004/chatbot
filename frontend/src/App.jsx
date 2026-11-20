import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Backend API URL (defaults to localhost:8000 or env variable for deployment)
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function generateSessionId() {
  return "s-" + Math.random().toString(36).substring(2, 10);
}

export default function App() {
  // A new session starts on each page load
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [simulateFailure, setSimulateFailure] = useState("");
  const [backendStatus, setBackendStatus] = useState(null);

  const endRef = useRef(null);

  // Initialize session on mount
  useEffect(() => {
    const newId = generateSessionId();
    setSessionId(newId);
    checkHealth();
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) {
        const data = await res.json();
        setBackendStatus(data);
      } else {
        setBackendStatus({ status: "error" });
      }
    } catch {
      setBackendStatus({ status: "offline" });
    }
  };

  const startNewSession = () => {
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([]);
    setInput("");
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMessage = {
      role: "user",
      content: trimmed,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const headers = {
        "Content-Type": "application/json",
      };

      if (simulateFailure) {
        headers["X-Simulate-Failure"] = simulateFailure;
      }

      const bodyPayload = {
        session_id: sessionId,
        message: trimmed,
      };

      if (systemPrompt.trim()) {
        bodyPayload.system_prompt = systemPrompt.trim();
      }

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

      const data = await response.json();

      if (!response.ok) {
        // Display readable error message in chat (never a blank screen)
        const errorDetail =
          data.detail && typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || "Request failed");

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            isError: true,
            status: response.status,
            content: `**Error (${response.status}):** ${errorDetail}`,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
        return;
      }

      // Successful assistant reply with metadata
      const assistantMessage = {
        role: "assistant",
        content: data.reply,
        metadata: data.metadata || {},
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          isError: true,
          content: `**Connection Error:** Unable to reach the backend at \`${API_BASE_URL}\`. Please verify the server is running.`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen text-white font-sans overflow-hidden">
      {/* Top Navbar */}
      <header className="h-16 border-b border-white/10 bg-white/5 backdrop-blur-xl px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600/30 border border-blue-500/40 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <span className="text-blue-400 font-bold text-lg">✦</span>
          </div>
          <div>
            <h1 className="font-semibold text-sm tracking-wide flex items-center gap-2">
              Lyftr AI Gateway
              <span className="text-[10px] uppercase tracking-wider bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30 font-mono">
                Failover & Cache
              </span>
            </h1>
            <p className="text-xs text-gray-400 font-mono">
              Session: <span className="text-blue-400 font-semibold">{sessionId}</span>
            </p>
          </div>
        </div>

        {/* Status & Quick Action */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-xs font-mono bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg">
            <span
              className={`w-2 h-2 rounded-full ${
                backendStatus?.status === "ok"
                  ? "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]"
                  : "bg-amber-400"
              }`}
            />
            <span className="text-gray-300">
              {backendStatus?.status === "ok"
                ? `Keys: ${backendStatus.keys_configured} | Cache: ${backendStatus.cache_enabled ? "ON" : "OFF"}`
                : "Checking backend..."}
            </span>
          </div>

          <button
            onClick={startNewSession}
            className="text-xs bg-white/10 hover:bg-white/15 border border-white/15 px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5"
            title="Start a new session on demand"
          >
            <span>+</span> New Session
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {/* Controls Sidebar */}
        <aside className="w-80 bg-white/[0.03] backdrop-blur-xl border-r border-white/10 flex flex-col p-5 shrink-0 hidden md:flex space-y-6 overflow-y-auto">
          {/* System Prompt Box */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
              <span>⚙️</span> System Prompt
            </label>
            <p className="text-[11px] text-gray-400 leading-relaxed">
              Overrides default instructions for this active session.
            </p>
            <textarea
              data-testid="system-prompt-input"
              rows={3}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="e.g. You are a concise and helpful AI technical assistant..."
              className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 resize-none font-sans"
            />
          </div>

          {/* Failover Test Hook */}
          <div className="space-y-2.5 bg-white/5 p-4 rounded-xl border border-white/10">
            <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span>⚡</span> Failover Test Hook
              </span>
              <span className="text-[10px] text-blue-400 lowercase font-mono">X-Simulate-Failure</span>
            </label>
            <p className="text-[11px] text-gray-400 leading-relaxed">
              Force key failure for one request to verify fallback without burning real API quota:
            </p>
            <select
              value={simulateFailure}
              onChange={(e) => setSimulateFailure(e.target.value)}
              className="w-full bg-[#0d1326] border border-white/20 rounded-lg p-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">None (Normal Execution)</option>
              <option value="key_1=429">key_1=429 (Fall back to key_2)</option>
              <option value="key_1=500">key_1=500 (Fall back to key_2)</option>
              <option value="*=429">*=429 (All keys fail -&gt; Clean 503)</option>
            </select>
          </div>

          {/* Quick Info / Assignment Spec Checklist */}
          <div className="flex-1 space-y-2.5 text-xs text-gray-400">
            <p className="font-semibold text-gray-300 uppercase tracking-wider text-[11px]">
              Behavior Guidelines
            </p>
            <div className="p-3 bg-white/[0.02] border border-white/5 rounded-lg space-y-1.5 text-[11px] leading-relaxed">
              <div className="flex items-start gap-1.5">
                <span className="text-blue-400">•</span>
                <span><strong>Multi-turn:</strong> Conversation history persisted per session in SQLite.</span>
              </div>
              <div className="flex items-start gap-1.5">
                <span className="text-green-400">•</span>
                <span><strong>Cache Hit:</strong> Identical message returns <code className="text-green-300">LLM_CACHE</code> with faster latency.</span>
              </div>
              <div className="flex items-start gap-1.5">
                <span className="text-purple-400">•</span>
                <span><strong>Key Pool:</strong> Automatic failover across configured keys on 429/5xx.</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Chat Area */}
        <main className="flex flex-col flex-1 relative min-w-0">
          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400">
                <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-2xl mb-4 shadow-inner">
                  💬
                </div>
                <h2 className="text-lg font-semibold text-white mb-1">Welcome to Lyftr AI Chatbot</h2>
                <p className="text-xs text-gray-400 max-w-md leading-relaxed">
                  Start typing to test multi-turn state, LiteLLM key failover resilience, response caching, and per-request token tracking.
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    {...(msg.role === "assistant" ? { "data-testid": "assistant-message" } : {})}
                    className={`max-w-[85%] md:max-w-[75%] px-5 py-4 rounded-2xl text-sm leading-relaxed shadow-lg backdrop-blur-md transition-all ${
                      msg.role === "user"
                        ? "bg-blue-600/90 text-white rounded-br-sm border border-blue-500/50"
                        : msg.isError
                        ? "bg-red-500/10 text-red-200 border border-red-500/30 rounded-bl-sm"
                        : "bg-white/10 text-gray-100 border border-white/10 rounded-bl-sm"
                    }`}
                  >
                    {/* Message Content */}
                    <div className="prose prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 text-sm">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>

                    {/* Metadata Footer for Assistant Messages */}
                    {msg.role === "assistant" && !msg.isError && msg.metadata && (
                      <div className="mt-3.5 pt-3 border-t border-white/10 flex flex-wrap items-center gap-2 text-[11px] font-mono">
                        {/* Resolution Source */}
                        <span
                          data-testid="meta-source"
                          className={`px-2 py-0.5 rounded-md font-semibold border ${
                            msg.metadata.resolution_source === "LLM_CACHE"
                              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-[0_0_8px_rgba(16,185,129,0.3)]"
                              : "bg-blue-500/20 text-blue-300 border-blue-500/40"
                          }`}
                        >
                          {msg.metadata.resolution_source || "LIVE_INFERENCE"}
                        </span>

                        {/* Model */}
                        <span
                          data-testid="meta-model"
                          className="bg-white/5 text-gray-300 px-2 py-0.5 rounded border border-white/10"
                        >
                          {msg.metadata.model || "unknown"}
                        </span>

                        {/* Latency */}
                        <span
                          data-testid="meta-latency"
                          className="bg-white/5 text-amber-300 px-2 py-0.5 rounded border border-white/10"
                        >
                          {msg.metadata.latency_ms !== undefined ? `${msg.metadata.latency_ms} ms` : "0 ms"}
                        </span>

                        {/* Input Tokens */}
                        <span className="bg-white/5 text-cyan-300 px-2 py-0.5 rounded border border-white/10">
                          in: <span data-testid="meta-input-tokens">{msg.metadata.input_tokens ?? 0}</span>
                        </span>

                        {/* Output Tokens */}
                        <span className="bg-white/5 text-pink-300 px-2 py-0.5 rounded border border-white/10">
                          out: <span data-testid="meta-output-tokens">{msg.metadata.output_tokens ?? 0}</span>
                        </span>

                        {/* Key Info / Failover attempts if present */}
                        {msg.metadata.key_id && (
                          <span className="bg-white/5 text-gray-400 px-1.5 py-0.5 rounded text-[10px]">
                            key: {msg.metadata.key_id}
                          </span>
                        )}
                        {msg.metadata.fallback_attempts > 0 && (
                          <span className="bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded text-[10px]">
                            retries: {msg.metadata.fallback_attempts}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {/* Typing Loader */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white/10 backdrop-blur-md text-gray-300 px-5 py-3 rounded-2xl rounded-bl-sm border border-white/10 flex items-center gap-2 text-xs">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" />
                    <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
                  <span>Waiting for LiteLLM inference / cache lookup...</span>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Bottom Chat Input */}
          <div className="p-4 bg-white/[0.02] border-t border-white/10">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center bg-white/5 backdrop-blur-md border border-white/15 rounded-xl px-4 py-2.5 shadow-xl focus-within:border-blue-500/60 focus-within:ring-1 focus-within:ring-blue-500/50 transition">
                <input
                  data-testid="chat-input"
                  className="flex-1 bg-transparent outline-none text-sm text-white placeholder-gray-400"
                  placeholder="Send a message (e.g. 'What is the capital of France?')..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  disabled={loading}
                />
                <button
                  data-testid="send-button"
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  className={`ml-3 px-4 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-1.5 ${
                    loading || !input.trim()
                      ? "bg-white/10 text-gray-400 cursor-not-allowed"
                      : "bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-500/20 active:scale-95"
                  }`}
                >
                  <span>Send</span>
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </div>

              <div className="flex items-center justify-between text-[11px] text-gray-500 mt-2 px-1">
                <span>Press <kbd className="px-1 py-0.5 bg-white/10 rounded text-[10px]">Enter ↵</kbd> to send</span>
                <span>Active Model: Gemini 2.0 Flash (via LiteLLM)</span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
