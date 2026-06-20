"use client";

import { useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

/**
 * The persistent, always-moving backdrop. Large blurred colour orbs drift on
 * CSS keyframes; the whole layer also parallaxes a few pixels toward the cursor
 * via springs, so it feels alive and "flows along" with every page. GPU-only
 * (transform/opacity), so it stays buttery smooth.
 */
export function AuroraBackground() {
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 40, damping: 20, mass: 0.6 });
  const sy = useSpring(my, { stiffness: 40, damping: 20, mass: 0.6 });

  // Two parallax depths
  const x1 = useTransform(sx, (v) => v * 24);
  const y1 = useTransform(sy, (v) => v * 24);
  const x2 = useTransform(sx, (v) => v * -14);
  const y2 = useTransform(sy, (v) => v * -14);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mx.set(e.clientX / window.innerWidth - 0.5);
      my.set(e.clientY / window.innerHeight - 0.5);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mx, my]);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#05060d]">
      {/* deep base gradient */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 90% at 50% -10%, #0b1024 0%, #06070f 55%, #04050b 100%)",
        }}
      />

      {/* drifting colour orbs — far layer */}
      <motion.div className="absolute inset-0" style={{ x: x1, y: y1 }}>
        <div
          className="absolute -top-40 -left-32 h-[42rem] w-[42rem] rounded-full opacity-60 blur-[120px]"
          style={{ background: "radial-gradient(circle, #22d3ee 0%, transparent 65%)", animation: "drift-a 26s ease-in-out infinite" }}
        />
        <div
          className="absolute top-1/3 -right-40 h-[40rem] w-[40rem] rounded-full opacity-55 blur-[120px]"
          style={{ background: "radial-gradient(circle, #8b5cf6 0%, transparent 65%)", animation: "drift-b 32s ease-in-out infinite" }}
        />
      </motion.div>

      {/* near layer */}
      <motion.div className="absolute inset-0" style={{ x: x2, y: y2 }}>
        <div
          className="absolute bottom-[-12rem] left-1/4 h-[38rem] w-[38rem] rounded-full opacity-45 blur-[130px]"
          style={{ background: "radial-gradient(circle, #34d399 0%, transparent 65%)", animation: "drift-c 30s ease-in-out infinite" }}
        />
        <div
          className="absolute top-10 left-1/2 h-[26rem] w-[26rem] rounded-full opacity-40 blur-[120px]"
          style={{ background: "radial-gradient(circle, #6366f1 0%, transparent 65%)", animation: "drift-a 24s ease-in-out infinite reverse" }}
        />
      </motion.div>

      {/* fine grid */}
      <div
        className="absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(120% 80% at 50% 20%, #000 30%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(120% 80% at 50% 20%, #000 30%, transparent 80%)",
        }}
      />

      {/* subtle grain + vignette for depth */}
      <div
        className="absolute inset-0 opacity-[0.05] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(120% 100% at 50% 50%, transparent 55%, rgba(0,0,0,.55) 100%)" }}
      />
    </div>
  );
}
