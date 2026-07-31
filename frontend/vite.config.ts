import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { visualizer } from 'rollup-plugin-visualizer'
import viteCompression from 'vite-plugin-compression'
import AutoImport from 'unplugin-auto-import/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ command, mode }) => {
  const isAnalyze = mode === 'analyze'

  return {
    base: '/',
    plugins: [
      vue(),
      vuetify({
        autoImport: true,
        styles: {
          configFile: 'src/styles/settings.scss',
        },
      }),
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia', '@vueuse/core'],
        dts: 'src/auto-imports.d.ts',
      }),
      viteCompression({ verbose: true, disable: false, threshold: 10240, algorithm: 'gzip', ext: '.gz' }),
      viteCompression({ verbose: true, disable: false, threshold: 10240, algorithm: 'brotliCompress', ext: '.br' }),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.ico', 'favicon-32x32.png', 'apple-touch-icon.png', 'favicon.svg'],
        manifest: {
          name: 'Anime Manager',
          short_name: '番剧管家',
          description: '全自动番剧识别与整理工具',
          theme_color: '#a855f7',
          background_color: '#0a0a1a',
          display: 'standalone',
          orientation: 'portrait',
          scope: '/',
          start_url: '/',
          icons: [
            { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
            { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
            { src: '/pwa-maskable-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
            { src: '/pwa-maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
          navigateFallback: 'index.html',
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              urlPattern: /\/api\//,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                networkTimeoutSeconds: 10,
                expiration: {
                  maxEntries: 100,
                  maxAgeSeconds: 60 * 60 * 24,
                },
                cacheableResponse: {
                  statuses: [0, 200],
                },
              },
            },
            {
              urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'image-cache',
                expiration: {
                  maxEntries: 200,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
              },
            },
          ],
        },
      }),
      isAnalyze && visualizer({ open: true, gzipSize: true, filename: 'dist/stats.html' }),
    ],
    define: {
      __APP_VERSION__: JSON.stringify('3.0.0'),
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        // 图片代理：不改 Origin，让浏览器原始 Host/Referer 保持一致，通过后端鉴权
        '/api/system/img': { target: 'http://apm-backend:8000' },
        '/api/system/bgm_img': { target: 'http://apm-backend:8000' },
        '/api/appearance/image': { target: 'http://apm-backend:8000' },
        // 其他 API：changeOrigin 保持原样
        '/api': { target: 'http://apm-backend:8000', changeOrigin: true },
        '/ws': { target: 'ws://apm-backend:8000', ws: true, changeOrigin: true },
        '/static': { target: 'http://apm-backend:8000', changeOrigin: true },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/vuetify') || id.includes('node_modules/.vite/deps/vuetify')) return 'vuetify'
            if (id.includes('node_modules/vue') || id.includes('node_modules/vue-router') || id.includes('node_modules/pinia')) return 'vue-vendor'
          },
        },
      },
      minify: true,
      cssMinify: false,
    },
  }
})
