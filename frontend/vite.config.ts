import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// M7: backend at :8000 serves the built bundle from / (static mount).
// Dev mode proxies /api → localhost:8000 so SSE/MJPEG/REST are real.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
        // SSE needs the raw stream — no buffering
        ws: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
});
