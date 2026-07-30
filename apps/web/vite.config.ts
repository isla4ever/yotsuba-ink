import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom', 'three'],
  },
  server: {
    proxy: {
      '/api': process.env.NOVEL_API_PROXY || 'http://127.0.0.1:8787',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          // 3D stack must stay out of the eager graph-vendor chunk: it is only
          // reachable via the lazy CharacterNetwork3DView import.
          if (/node_modules\/(react-force-graph-3d|3d-force-graph|three|three-forcegraph|three-render-objects)\//.test(id)) {
            return 'graph-3d-vendor';
          }
          if (id.includes('react-force-graph-2d') || id.includes('force-graph')) {
            return 'graph-vendor';
          }
          if (id.includes('@xyflow/react')) {
            return 'flow-vendor';
          }
          if (id.includes('@base-ui/react')) {
            return 'base-ui-vendor';
          }
          if (id.includes('@radix-ui')) {
            return 'radix-vendor';
          }
          return undefined;
        },
      },
    },
  },
});
