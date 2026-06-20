import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8787',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('react-force-graph-2d') || id.includes('force-graph')) {
            return 'graph-vendor';
          }
          if (id.includes('@xyflow/react')) {
            return 'flow-vendor';
          }
          return undefined;
        },
      },
    },
  },
});
