import path from 'node:path'
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Enable React strict mode
  reactStrictMode: true,
  turbopack: {
    root: path.resolve(__dirname, '..'),
  },

  // Optimize images
  images: {
    unoptimized: true,
  },

  async rewrites() {
    const backendUrl = process.env.AGENT_BACKEND_URL?.replace(/\/$/, '')
    if (!backendUrl) {
      return []
    }

    return [
      {
        source: '/api/get_config',
        destination: `${backendUrl}/get_config`,
      },
      {
        source: '/api/startAgent',
        destination: `${backendUrl}/startAgent`,
      },
      {
        source: '/api/stopAgent',
        destination: `${backendUrl}/stopAgent`,
      },
      {
        source: '/api/ncsNotify',
        destination: `${backendUrl}/ncsNotify`,
      },
      {
        source: '/api/webhooks/stream',
        destination: `${backendUrl}/webhooks/stream`,
      },
      {
        source: '/api/webhooks/reset',
        destination: `${backendUrl}/webhooks/reset`,
      },
    ]
  },
}

export default nextConfig
