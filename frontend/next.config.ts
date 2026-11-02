import type { NextConfig } from "next";

// The browser only ever talks to this origin. /api/* is proxied to FastAPI so the session cookie is
// first-party (SameSite=Lax, HttpOnly) and no API secrets reach the client bundle.
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Docker builds set NEXT_OUTPUT=standalone; local `next start` uses the default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  images: {
    remotePatterns: [{ protocol: "https", hostname: "render.worldofwarcraft.com" }],
  },
};

export default nextConfig;
