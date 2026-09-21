import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // native module: keep it out of the bundler
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;
