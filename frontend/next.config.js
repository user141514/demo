const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_STANDALONE === "true" ? "standalone" : undefined,
  outputFileTracingRoot: path.resolve(__dirname),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/health`,
      },
      {
        source: "/docs",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/openapi.json`,
      },
    ];
  },
};

module.exports = nextConfig;

