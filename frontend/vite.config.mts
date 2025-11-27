import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/v1': 'http://localhost:8000' } },
    optimizeDeps: {
    // Avoid Vite trying to crawl *.mjs in dist and picking stale filenames
    exclude: ['onnxruntime-web'],
  },
  ssr: {
    // for dev tools / tests that run SSR, keep it externalized correctly
    noExternal: ['onnxruntime-web'],
  },
})
