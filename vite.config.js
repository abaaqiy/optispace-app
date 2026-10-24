import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],

  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,

    watch: {
      // These belong to Python, not the React frontend.
      ignored: [
        '**/.venv/**',
        '**/venv/**',
        '**/backend/**',
        '**/__pycache__/**',
      ],

      // Avoid the operating system's file-watcher limit.
      usePolling: true,
      interval: 1000,
    },

    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/static': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});

