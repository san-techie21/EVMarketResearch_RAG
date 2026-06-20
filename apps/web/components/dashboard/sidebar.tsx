"use client";

import { motion } from "framer-motion";
import { Plus, MessageSquare, BarChart3, LogOut, Zap } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { RECENT_CHATS } from "@/lib/mock";
import { cn } from "@/lib/utils";

export type View = "chat" | "insights";

export function Sidebar({
  view,
  onView,
  onNewChat,
  onSignOut,
}: {
  view: View;
  onView: (v: View) => void;
  onNewChat: () => void;
  onSignOut: () => void;
}) {
  return (
    <motion.aside
      initial={{ x: -24, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 90, damping: 18 }}
      className="glass relative z-20 flex h-screen w-[270px] shrink-0 flex-col rounded-r-3xl p-4"
    >
      {/* brand */}
      <div className="flex items-center gap-2.5 px-1 pb-4">
        <BrandLogo size={36} glow={false} />
        <div>
          <p className="text-[15px] font-semibold leading-none tracking-tight">Voltaic</p>
          <p className="mt-1 text-[10.5px] text-[var(--text-3)]">Market Intelligence</p>
        </div>
      </div>

      {/* new chat */}
      <button
        onClick={onNewChat}
        className="glass-hover group flex items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-sm font-medium"
      >
        <Plus className="h-4 w-4 text-[var(--accent-cyan)] transition-transform group-hover:rotate-90" />
        New chat
      </button>

      {/* nav */}
      <nav className="mt-5 space-y-1">
        <NavItem active={view === "chat"} onClick={() => onView("chat")} icon={MessageSquare} label="Chat" />
        <NavItem active={view === "insights"} onClick={() => onView("insights")} icon={BarChart3} label="Market Pulse" badge="new" />
      </nav>

      {/* recents */}
      <p className="mt-6 mb-1.5 px-2 text-[10.5px] font-semibold uppercase tracking-wider text-[var(--text-3)]">
        Recent
      </p>
      <div className="flex-1 space-y-0.5 overflow-y-auto pr-1">
        {RECENT_CHATS.map((c) => (
          <button
            key={c.id}
            onClick={() => onView("chat")}
            className="group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition hover:bg-white/[0.05]"
          >
            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[var(--text-3)] group-hover:text-[var(--text-2)]" />
            <span className="flex-1 truncate text-[13px] text-[var(--text-2)] group-hover:text-[var(--text)]">
              {c.title}
            </span>
            <span className="text-[10px] text-[var(--text-3)]">{c.when}</span>
          </button>
        ))}
      </div>

      {/* user */}
      <div className="mt-3 flex items-center gap-2.5 rounded-xl glass px-3 py-2.5">
        <div className="grid h-8 w-8 place-items-center rounded-full brand-gradient text-xs font-bold text-white">
          A
        </div>
        <div className="flex-1 leading-tight">
          <p className="text-[13px] font-medium">Analyst</p>
          <p className="flex items-center gap-1 text-[10.5px] text-[var(--accent-emerald)]">
            <Zap className="h-2.5 w-2.5" fill="currentColor" /> Live workspace
          </p>
        </div>
        <button onClick={onSignOut} title="Sign out" className="rounded-lg p-1.5 text-[var(--text-3)] transition hover:bg-white/10 hover:text-[var(--text)]">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </motion.aside>
  );
}

function NavItem({
  active, onClick, icon: Icon, label, badge,
}: {
  active: boolean; onClick: () => void; icon: typeof MessageSquare; label: string; badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition",
        active ? "text-[var(--text)]" : "text-[var(--text-2)] hover:bg-white/[0.05]",
      )}
    >
      {active && (
        <motion.span
          layoutId="nav-active"
          className="absolute inset-0 rounded-xl glass-2"
          transition={{ type: "spring", stiffness: 280, damping: 28 }}
        />
      )}
      <Icon className={cn("relative h-4 w-4", active && "text-[var(--accent-cyan)]")} />
      <span className="relative font-medium">{label}</span>
      {badge && (
        <span className="relative ml-auto rounded-full bg-[var(--accent-violet)]/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[var(--accent-violet)]">
          {badge}
        </span>
      )}
    </button>
  );
}
