import { ref, type Ref } from 'vue'

interface Composer {
  t: (key: string, ...args: unknown[]) => string
  locale: Ref<string>
}

interface I18n {
  global: Composer
  install: (app: { use: (plugin: unknown) => void }) => void
}

interface I18nOptions {
  legacy?: boolean
  locale?: string
  fallbackLocale?: string
  messages?: Record<string, Record<string, unknown>>
}

const messages = ref<Record<string, Record<string, unknown>>>({})
const locale = ref('zh-CN')

function resolveKey(obj: Record<string, unknown>, path: string): string {
  const parts = path.split('.')
  let current: unknown = obj
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = (current as Record<string, unknown>)[part]
    } else {
      return path
    }
  }
  return typeof current === 'string' ? current : path
}

function t(key: string): string {
  const msg = messages.value[locale.value]
  if (!msg) return key
  return resolveKey(msg, key)
}

export function createI18n(options: I18nOptions): I18n {
  if (options.messages) {
    messages.value = options.messages
  }
  if (options.locale) {
    locale.value = options.locale
  }

  return {
    global: { t, locale },
    install(app) {
      app.use({ install: () => {} })
    },
  }
}

export function useI18n(): Composer {
  return { t, locale }
}
