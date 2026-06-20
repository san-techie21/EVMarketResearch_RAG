"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Mail, Lock, Sparkles, ShieldCheck, Newspaper, BarChart3 } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { login, isLive } from "@/lib/api";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 120, damping: 16 } },
};

const FEATURES = [
  { icon: BarChart3, text: "24,863 chunks across 12 EV & energy apps" },
  { icon: Newspaper, text: "Live news, reviews, video & web - one brain" },
  { icon: ShieldCheck, text: "Every answer cited back to its source" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("analyst@voltaic.ai");
  const [password, setPassword] = useState("demo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const ok = await login(email, password);
    if (ok) {
      router.push("/dashboard");
    } else {
      setLoading(false);
      setError("Invalid username or password.");
    }
  }

  return (
    <main className="min-h-screen w-full px-5 py-10 lg:px-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
        {/* -- Hero side ----------------------------------------------- */}
        <motion.section
          variants={container}
          initial="hidden"
          animate="show"
          className="hidden flex-col lg:flex"
        >
          <motion.div variants={item} className="flex items-center gap-3">
            <BrandLogo size={48} />
            <div>
              <p className="text-xl font-semibold tracking-tight">Voltaic</p>
              <p className="text-xs text-[var(--text-3)]">EV &amp; Energy Market Intelligence</p>
            </div>
          </motion.div>

          <motion.h1
            variants={item}
            className="mt-10 text-5xl font-bold leading-[1.05] tracking-tight"
          >
            The competitive brain for
            <br />
            <span className="text-gradient">EV charging &amp; home energy.</span>
          </motion.h1>

          <motion.p variants={item} className="mt-5 max-w-md text-[15px] leading-relaxed text-[var(--text-2)]">
            Ask anything about the market. Voltaic reads every review, news article,
            video and website across the top apps and answers in seconds - with
            receipts.
          </motion.p>

          <motion.ul variants={item} className="mt-9 space-y-3">
            {FEATURES.map((f) => (
              <li key={f.text} className="flex items-center gap-3 text-sm text-[var(--text-2)]">
                <span className="grid h-8 w-8 place-items-center rounded-lg glass">
                  <f.icon className="h-4 w-4 text-[var(--accent-cyan)]" />
                </span>
                {f.text}
              </li>
            ))}
          </motion.ul>
        </motion.section>

        {/* -- Login card ---------------------------------------------- */}
        <motion.section
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ type: "spring", stiffness: 90, damping: 16, delay: 0.15 }}
          className="glass-2 relative mx-auto w-full max-w-[420px] overflow-hidden rounded-3xl p-8"
        >
          {/* top sheen */}
          <div className="pointer-events-none absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />

          <div className="mb-7 flex flex-col items-center text-center lg:hidden">
            <BrandLogo size={52} />
            <h2 className="mt-3 text-lg font-semibold">Voltaic</h2>
          </div>

          <div className="mb-6">
            <h2 className="text-[22px] font-semibold tracking-tight">Welcome back</h2>
            <p className="mt-1 text-sm text-[var(--text-3)]">Sign in to your intelligence workspace</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <Field
              icon={<Mail className="h-4 w-4" />}
              label="Email or username"
              type="text"
              value={email}
              onChange={setEmail}
              placeholder="you@company.com or admin"
            />
            <Field
              icon={<Lock className="h-4 w-4" />}
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
            />

            <button
              type="submit"
              disabled={loading}
              className="group relative mt-2 flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl brand-gradient px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-900/40 transition-transform active:scale-[.98] disabled:opacity-80"
            >
              {/* shine sweep */}
              <span className="pointer-events-none absolute inset-0 overflow-hidden">
                <span
                  className="absolute top-0 left-0 h-full w-1/3 bg-white/25 blur-md transition-transform duration-700 group-hover:translate-x-[260%]"
                  style={{ transform: "translateX(-150%) skewX(-18deg)" }}
                />
              </span>
              {loading ? "Entering…" : "Enter workspace"}
              {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
            </button>

            {error && <p className="text-center text-xs text-rose-400">{error}</p>}
          </form>

          <div className="mt-5 flex items-center gap-2 rounded-xl glass px-3 py-2.5 text-xs text-[var(--text-2)]">
            <Sparkles className="h-3.5 w-3.5 text-[var(--accent-violet)]" />
            {isLive() ? (
              <>Connected to your live workspace.</>
            ) : (
              <>Demo mode - credentials are prefilled. Just hit <b className="text-[var(--text)]">Enter workspace</b>.</>
            )}
          </div>
        </motion.section>
      </div>
    </main>
  );
}

function Field({
  icon, label, type, value, onChange, placeholder,
}: {
  icon: React.ReactNode; label: string; type: string;
  value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[var(--text-2)]">{label}</span>
      <div className="group flex items-center gap-2.5 rounded-xl glass px-3.5 py-3 transition focus-within:border-[var(--accent-blue)] focus-within:glow-ring">
        <span className="text-[var(--text-3)] transition group-focus-within:text-[var(--accent-blue)]">{icon}</span>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm text-[var(--text)] placeholder:text-[var(--text-3)] outline-none"
        />
      </div>
    </label>
  );
}
