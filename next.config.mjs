const configuredBasePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  basePath: configuredBasePath,
  assetPrefix: configuredBasePath || undefined,
  images: {
    unoptimized: true
  },
  trailingSlash: true
};

export default nextConfig;
