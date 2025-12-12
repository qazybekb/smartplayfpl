/** @type {import('next').NextConfig} */

// =============================================================================
// Environment Configuration
// =============================================================================
// Development: Uses localhost backend (http://localhost:8000)
// Production: Uses Railway backend (set via NEXT_PUBLIC_API_URL in Vercel)
//
// Detection priority:
// 1. NEXT_PUBLIC_API_URL environment variable (explicit override)
// 2. VERCEL environment variable (true = production on Vercel)
// 3. NODE_ENV (development vs production)

const PRODUCTION_BACKEND_URL = 'https://smartplayfpl-backend-production.up.railway.app';
const DEVELOPMENT_BACKEND_URL = 'http://localhost:8000';

function getBackendUrl() {
  // 1. Check for explicit API URL override
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  // 2. Check if running on Vercel (production)
  if (process.env.VERCEL) {
    return PRODUCTION_BACKEND_URL;
  }

  // 3. Check NODE_ENV
  if (process.env.NODE_ENV === 'production') {
    return PRODUCTION_BACKEND_URL;
  }

  // 4. Default to development
  return DEVELOPMENT_BACKEND_URL;
}

const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    const backendUrl = getBackendUrl();

    // Log backend URL during build (helps with debugging)
    console.log(`[Next.js Config] Backend URL: ${backendUrl}`);
    console.log(`[Next.js Config] Environment: ${process.env.NODE_ENV}`);
    console.log(`[Next.js Config] VERCEL: ${process.env.VERCEL || 'false'}`);

    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },

  // Configure dev server
  ...(process.env.NODE_ENV === 'development' && {
    experimental: {
      serverActions: {
        bodySizeLimit: '2mb',
      },
    },
  }),
};

module.exports = nextConfig;
