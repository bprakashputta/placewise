import type { NextConfig } from "next";

// The browser only ever talks to this Next.js server. ONLY /api/* is proxied to the
// FastAPI container's /api/* routes over the internal Docker network. API docs, /livez
// and dev routes live outside /api and are never reachable through the web origin.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Hide the dev-mode route indicator (it overlaps the UI in demos); errors still surface.
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` }];
  },
};

export default nextConfig;
