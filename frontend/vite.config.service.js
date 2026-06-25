import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'serve-service-html',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url === '/' || req.url === '/index.html') {
            req.url = '/service.html'
          }
          next()
        })
      },
    },
  ],
  server: {
    port: 8094,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
      '/ws': { target: 'ws://127.0.0.1:8010', ws: true },
    },
  },
  build: {
    outDir: 'dist-service',
    rollupOptions: {
      input: { main: 'service.html' },
    },
  },
})
