/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The prototype runs fully on-premise. No external image domains, no telemetry.
  images: { unoptimized: true },
  eslint: { ignoreDuringBuilds: true },
  env: {
    // Base URL for the optional FastAPI backend. The UI runs standalone on baked
    // mock data by default, so sample workflows work even if the backend is offline.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
