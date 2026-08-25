import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  reactStrictMode: true,
  logging: {
    incomingRequests: {
      ignore: [/^\/auth\/callback(?:[/?]|$)/]
    }
  }
};

export default nextConfig;
