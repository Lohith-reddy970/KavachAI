/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The app runs on-premise. No external image domains, no telemetry.
  images: { unoptimized: true },
  eslint: { ignoreDuringBuilds: true },
  env: {
    // Browser-accessible local backend URL, set at build time.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
