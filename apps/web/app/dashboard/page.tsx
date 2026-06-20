"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Activity } from "lucide-react";
import { Sidebar, type View } from "@/components/dashboard/sidebar";
import { ChatView } from "@/components/dashboard/chat-view";
import { InsightsView } from "@/components/dashboard/insights-view";

const CATEGORIES = ["All", "EV Charging", "Prosumer"] as const;

export default function DashboardPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [view, setView] = useState<View>("chat");
  const [chatKey, setChatKey] = useState(0);
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("All");

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("voltaic_auth") !== "1") {
      router.replace("/");
    } else {
      setReady(true);
    }
  }, [router]);

  if (!ready) return null;

  function signOut() {
    localStorage.removeItem("voltaic_auth");
    router.replace("/");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        view={view}
        onView={setView}
        onNewChat={() => {
          setChatKey((k) => k + 1);
          setView("chat");
        }}
        onSignOut={signOut}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        {/* topbar */}
        <header className="z-10 flex items-center gap-4 px-6 py-3.5">
          <div className="flex-1">
            <h1 className="text-[15px] font-semibold tracking-tight">
              {view === "chat" ? "Research Chat" : "Market Pulse"}
            </h1>
          </div>

          {view === "chat" && (
            <div className="hidden items-center gap-1 rounded-xl glass p-1 sm:flex">
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  className="relative rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition"
                >
                  {category === c && (
                    <motion.span
                      layoutId="cat-active"
                      className="absolute inset-0 rounded-lg brand-gradient opacity-90"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                  <span className={category === c ? "relative text-white" : "relative text-[var(--text-2)]"}>
                    {c}
                  </span>
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 rounded-xl glass px-3 py-1.5 text-[12px] text-[var(--text-2)]">
            <Activity className="h-3.5 w-3.5 text-[var(--accent-emerald)]" />
            <span className="hidden md:inline">Knowledge base</span>
            <span className="font-semibold text-[var(--text)]">live</span>
          </div>
        </header>

        {/* view */}
        <div className="min-h-0 flex-1">
          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="h-full"
            >
              {view === "chat" ? <ChatView key={chatKey} /> : <InsightsView />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
