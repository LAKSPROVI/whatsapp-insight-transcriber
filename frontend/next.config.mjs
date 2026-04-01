/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://77.42.68.212:8020"}/api/:path*`,
      },
    ];
  },
  images: {
    domains: ["localhost", "77.42.68.212", "transcriber.jurislaw.com.br"],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://77.42.68.212:8020",
  },
};

export default nextConfig;
