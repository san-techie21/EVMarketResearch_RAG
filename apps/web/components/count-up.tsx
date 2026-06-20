"use client";

import { useEffect, useState } from "react";
import { animate } from "framer-motion";

export function CountUp({
  to,
  duration = 1.4,
  suffix = "",
}: {
  to: number;
  duration?: number;
  suffix?: string;
}) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    const controls = animate(0, to, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setVal(v),
    });
    return () => controls.stop();
  }, [to, duration]);
  return <>{Math.round(val).toLocaleString()}{suffix}</>;
}
