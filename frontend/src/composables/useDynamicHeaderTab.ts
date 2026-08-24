import type { ComputedRef, Ref } from 'vue'

export interface DynamicHeaderTabItem {
  title: string
  icon?: string
  tab: string
}

export interface DynamicHeaderTabButton {
  icon: string
  text?: string
  color?: string | ComputedRef<string>
  variant?: 'flat' | 'text' | 'elevated' | 'tonal' | 'outlined' | 'plain'
  size?: string
  class?: string
  action?: () => void
  show?: boolean | ComputedRef<boolean>
  loading?: boolean | ComputedRef<boolean>
}

interface DynamicHeaderTabConfig {
  items: DynamicHeaderTabItem[]
  modelValue: string
  appendButtons?: DynamicHeaderTabButton[]
  routePath?: string
  onUpdateModelValue?: (value: string) => void
}

/**
 * 动态顶栏 Tab — 供页面注册 Tab 到顶栏内部。
 * 参照 MoviePilot 的 useDynamicHeaderTab，简化版。
 * 页面调用 registerHeaderTab 后，Tab 会渲染在顶栏 <header> 内部，
 * 与顶栏共享玻璃材质和水纹效果。
 */
export function useDynamicHeaderTab() {
  const route = useRoute()

  const registerDynamicHeaderTab = inject<(tab: DynamicHeaderTabConfig) => void>('registerDynamicHeaderTab')
  const unregisterDynamicHeaderTab = inject<(routePath?: string) => void>('unregisterDynamicHeaderTab')

  const registerHeaderTab = (config: {
    items: DynamicHeaderTabItem[] | ComputedRef<DynamicHeaderTabItem[]> | Ref<DynamicHeaderTabItem[]>
    modelValue: Ref<string>
    appendButtons?: DynamicHeaderTabButton[]
  }) => {
    const tabConfig: DynamicHeaderTabConfig = {
      items: Array.isArray(config.items) ? config.items : config.items.value,
      modelValue: config.modelValue.value,
      appendButtons: config.appendButtons,
      routePath: route.path,
      onUpdateModelValue: (value: string) => {
        config.modelValue.value = value
      },
    }

    // 监听 modelValue 变化并更新
    watch(config.modelValue, newValue => {
      tabConfig.modelValue = newValue
      registerDynamicHeaderTab?.(tabConfig)
    })

    // 如果 items 是 computed/ref，也监听
    if (!Array.isArray(config.items)) {
      watch(
        config.items,
        newItems => {
          tabConfig.items = newItems
          registerDynamicHeaderTab?.(tabConfig)
        },
        { deep: true },
      )
    }

    const doRegister = () => {
      tabConfig.routePath = route.path
      tabConfig.items = Array.isArray(config.items) ? config.items : config.items.value
      tabConfig.modelValue = config.modelValue.value
      registerDynamicHeaderTab?.(tabConfig)
    }

    const doUnregister = () => {
      unregisterDynamicHeaderTab?.(tabConfig.routePath)
    }

    onBeforeMount(doRegister)
    onActivated(doRegister)
    onDeactivated(doUnregister)
    onUnmounted(doUnregister)
  }

  const unregisterHeaderTab = () => {
    unregisterDynamicHeaderTab?.()
  }

  return {
    registerHeaderTab,
    unregisterHeaderTab,
  }
}
