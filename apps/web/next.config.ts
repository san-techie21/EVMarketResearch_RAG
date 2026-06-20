import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 'standalone' produces a self-contained server bundle for the Docker image
  // (infra/docker-compose.yml `web` service). Vercel ignores this and uses its
  // own build, so it's safe in both targets.
  output: "standalone",
  env: {
    // Point the UI at the FastAPI backend when one is wired up. Falls back to
    // demo mode (mock data) when unset, so the app runs standalone on Vercel.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "",
  },
};

export default nextConfig;
