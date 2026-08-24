declare module 'vue-i18n' {
  import type { Ref } from 'vue'

  export interface I18nOptions {
    legacy?: boolean
    locale?: string
    fallbackLocale?: string
    messages?: Record<string, Record<string, unknown>>
  }

  export interface Composer {
    t: (key: string, ...args: unknown[]) => string
    locale: Ref<string>
  }

  export interface I18n {
    global: Composer
    install: (app: unknown) => void
  }

  export function createI18n(options: I18nOptions): I18n

  export function useI18n(): Composer
}
