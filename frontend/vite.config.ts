import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { visualizer } from 'rollup-plugin-visualizer'
import viteCompression from 'vite-plugin-compression'
import AutoImport from 'unplugin-auto-import/vite'
import { VitePWA } from 'vite-plugin-pwa'

// 从 package.json 统一读取版本号，避免多处硬编码
const pkgVersion = JSON.parse(readFileSync(fileURLToPath(new URL('./package.json', import.meta.url)), 'utf-8')).version

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
      __APP_VERSION__: JSON.stringify(pkgVersion),
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        'vue-i18n': fileURLToPath(new URL('./src/shims/vue-i18n.ts', import.meta.url)),
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
          // Vite 8 使用 Rolldown，manualChunks 函数返回 undefined 会报错，对象形式则报 "is not a function"
          // 改用 Rolldown 原生 advancedChunks.groups 配置，每个 group 用 name(字符串) + test(正则) 匹配
          // 使用 as any 绕过 Vite 旧版 Rollup 类型定义中缺少 advancedChunks 的问题
          advancedChunks: {
            groups: [
              { name: 'vuetify', test: /[\\/]node_modules[\\/](@?vuetify|vuetify)[\\/]/ },
              { name: 'vue-vendor', test: /[\\/]node_modules[\\/](@?vue|vue-router|pinia|@vueuse)[\\/]/ },
            ],
          },
        } as any,
      },
      minify: true,
      cssMinify: false,
    },
  }
})
