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
    port: 8095,
    proxy: {
      '/api': 'http://127.0.0.1:8012',
      '/ws': { target: 'ws://127.0.0.1:8012', ws: true },
    },
  },
  build: {
    outDir: 'dist-service',
    rollupOptions: {
      input: { main: 'service.html' },
    },
  },
})
