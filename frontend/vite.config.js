import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8093,
    proxy: {
      '/api': 'http://127.0.0.1:8011',
      '/ws': { target: 'ws://127.0.0.1:8011', ws: true },
    },
  },
  build: {
    outDir: 'dist-admin',
    rollupOptions: {
      input: { main: 'index.html' },
    },
  },
})
