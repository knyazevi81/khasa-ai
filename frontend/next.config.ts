import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Прокси /api на backend изнутри Next.js (если кто-то ходит мимо nginx —
  // например, в dev без nginx).
  async rewrites() {
    const target = process.env.INTERNAL_API_URL || "http://backend:8000";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
};

export default nextConfig;
