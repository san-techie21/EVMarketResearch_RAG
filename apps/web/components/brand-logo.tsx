"use client";

import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";

export function BrandLogo({
  size = 44,
  glow = true,
  className,
}: {
  size?: number;
  glow?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative grid place-items-center rounded-2xl brand-gradient",
        glow && "animate-glow",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <div className="absolute inset-px rounded-[14px] bg-white/10 backdrop-blur-sm" />
      <Zap
        className="relative text-white drop-shadow"
        style={{ width: size * 0.5, height: size * 0.5 }}
        strokeWidth={2.4}
        fill="white"
      />
    </div>
  );
}
