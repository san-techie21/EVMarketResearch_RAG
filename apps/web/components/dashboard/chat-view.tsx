"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, Sparkles, FileText, ChevronDown } from "lucide-react";
import { Markdown } from "@/components/markdown";
import {
  APPS, SOURCE_LABELS, EXAMPLE_QUESTIONS, answerFor, type Source,
} from "@/lib/mock";

interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  thinking?: boolean;
}

const appName = (slug: string) => APPS.find((a) => a.slug === slug)?.name ?? slug;
const appAccent = (slug: string) => APPS.find((a) => a.slug === slug)?.accent ?? "#818cf8";

export function ChatView() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    const userId = crypto.randomUUID();
    const aId = crypto.randomUUID();
    setMessages((m) => [
      ...m,
      { id: userId, role: "user", content: text },
      { id: aId, role: "assistant", content: "", thinking: true },
    ]);
    setInput("");

    // route the question to the most relevant answer, then stream it word-by-word
    const { answer, sources } = answerFor(text);
    setTimeout(() => {
      const tokens = answer.split(/(\s+)/);
      let i = 0;
      const timer = setInterval(() => {
        i += 2;
        const partial = tokens.slice(0, i).join("");
        const done = i >= tokens.length;
        setMessages((m) =>
          m.map((msg) =>
            msg.id === aId
              ? { ...msg, content: partial, thinking: false, sources: done ? sources : undefined }
              : msg,
          ),
        );
        if (done) {
          clearInterval(timer);
          setBusy(false);
        }
      }, 22);
    }, 650);
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
        <div className="mx-auto max-w-3xl">
          {empty ? (
            <EmptyState onPick={send} />
          ) : (
            <div className="space-y-6">
              <AnimatePresence initial={false}>
                {messages.map((m) =>
                  m.role === "user" ? (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex justify-end"
                    >
                      <div className="glass-2 max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5 text-[14.5px]">
                        {m.content}
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex gap-3"
                    >
                      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl brand-gradient">
                        <Sparkles className="h-4 w-4 text-white" />
                      </div>
                      <div className="min-w-0 flex-1">
                        {m.thinking ? (
                          <Thinking />
                        ) : (
                          <>
                            <Markdown text={m.content} />
                            {m.sources && m.sources.length > 0 && <Sources sources={m.sources} />}
                          </>
                        )}
                      </div>
                    </motion.div>
                  ),
                )}
              </AnimatePresence>
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* input */}
      <div className="px-4 pb-5 md:px-8">
        <div className="mx-auto max-w-3xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="glass-2 flex items-end gap-2 rounded-2xl p-2 pl-4 transition focus-within:glow-ring"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Ask about EV charging or home-energy apps…"
              className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[14.5px] text-[var(--text)] placeholder:text-[var(--text-3)] outline-none"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl brand-gradient text-white transition active:scale-95 disabled:opacity-40"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </form>
          <p className="mt-2 text-center text-[11px] text-[var(--text-3)]">
            Voltaic searches reviews, news, video &amp; web - answers are cited. Demo data.
          </p>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center pt-10 text-center"
    >
      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
        className="grid h-16 w-16 place-items-center rounded-2xl brand-gradient animate-glow"
      >
        <Sparkles className="h-7 w-7 text-white" />
      </motion.div>
      <h2 className="mt-6 text-2xl font-semibold tracking-tight">
        Ask anything about the <span className="text-gradient">EV &amp; energy</span> market
      </h2>
      <p className="mt-2 max-w-md text-sm text-[var(--text-2)]">
        Reviews, news, videos and websites across 12 apps - distilled into cited answers.
      </p>

      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {EXAMPLE_QUESTIONS.map((e, i) => (
          <motion.button
            key={e.q}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.07 }}
            whileHover={{ y: -3 }}
            onClick={() => onPick(e.q)}
            className="glass glass-hover group rounded-2xl p-4 text-left"
          >
            <span className="mb-2 inline-block rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--accent-cyan)]">
              {e.tag}
            </span>
            <p className="text-[13.5px] leading-snug text-[var(--text-2)] group-hover:text-[var(--text)]">
              {e.q}
            </p>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}

function Thinking() {
  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center gap-2 text-[13px] text-[var(--text-3)]">
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-[var(--accent-cyan)]"
              style={{ animation: "dot-bounce 1.2s ease-in-out infinite", animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </span>
        Searching knowledge base &amp; reranking sources…
      </div>
      <div className="shimmer h-3 w-3/4 rounded" />
      <div className="shimmer h-3 w-1/2 rounded" />
    </div>
  );
}

function Sources({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="glass glass-hover flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-[var(--text-2)]"
      >
        <FileText className="h-3.5 w-3.5 text-[var(--accent-violet)]" />
        {sources.length} cited sources
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      <div className="mt-2 flex flex-wrap gap-2">
        {sources.map((s, i) => (
          <span
            key={i}
            className="glass flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px]"
            style={{ borderColor: `${appAccent(s.app)}40` }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: appAccent(s.app) }} />
            <span className="font-medium text-[var(--text)]">{appName(s.app)}</span>
            <span className="text-[var(--text-3)]">{SOURCE_LABELS[s.source]}</span>
            <span className="text-[var(--accent-emerald)]">{s.score.toFixed(2)}</span>
          </span>
        ))}
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 space-y-2 overflow-hidden"
          >
            {sources.map((s, i) => (
              <div key={i} className="glass rounded-xl p-3">
                <div className="mb-1 flex items-center gap-2 text-[11px]">
                  <span className="font-semibold text-[var(--text)]">{appName(s.app)}</span>
                  <span className="text-[var(--text-3)]">· {SOURCE_LABELS[s.source]}</span>
                  <span className="ml-auto text-[var(--accent-emerald)]">score {s.score.toFixed(3)}</span>
                </div>
                <p className="text-[12.5px] leading-relaxed text-[var(--text-2)]">{s.snippet}</p>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
