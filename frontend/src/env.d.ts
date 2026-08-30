/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare const __APP_VERSION__: string

declare module '*.md?raw' {
  const content: string
  export default content
}

declare module 'markdown-it-link-attributes' {
  const plugin: (md: unknown, options?: Record<string, unknown>) => void
  export default plugin
}
