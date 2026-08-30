import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        // A genuinely separate HTML entry point for Neighborhood
        // Insights (not just index.html with a different client-side
        // title) — the only way its own static, crawler-visible SEO/
        // social-share metadata actually works, matching AccidentIQ's
        // own real approach for its sibling Travel Safety page.
        // Named "index" (not "main") specifically so the existing
        // app's own output chunk naming (index-*.js/css) stays
        // unchanged — minimizing the footprint of this change beyond
        // what's actually needed for the new page.
        index: resolve(__dirname, 'index.html'),
        neighborhoodInsights: resolve(__dirname, 'neighborhood-insights.html'),
      },
    },
  },
})
