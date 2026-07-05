<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTimePicker } from 'naive-ui'
import { appearanceConfig } from '../store/appearanceStore'
import { isDarkMode } from '../store/themeStore'

const timeRef = ref<HTMLElement | null>(null)

const props = withDefaults(defineProps<{
  value: string | null
  label: string
  placeholder?: string
  valueFormat?: string
  format?: string
  size?: 'tiny' | 'small' | 'medium' | 'large'
  disabled?: boolean
}>(), {
  valueFormat: 'HH:mm',
  format: 'HH:mm',
  size: 'small'
})

const emit = defineEmits<{
  (e: 'update:value', value: string | null): void
  (e: 'update:formattedValue', value: string | null): void
  (e: 'blur', event: FocusEvent): void
}>()

const focused = ref(false)

const hasValue = computed(() => props.value !== '' && props.value != null)
const isFloated = computed(() => focused.value || hasValue.value)
const showPlaceholder = computed(() =>
  (!props.label || focused.value || hasValue.value) ? props.placeholder : ''
)

const handleUpdateFormattedValue = (val: string | null) => {
  emit('update:formattedValue', val)
  emit('update:value', val)
}

// 动态生成 themeOverrides，用 JS 预计算 rgba 值（Naive UI 不接受 color-mix()）
// 注意：Naive UI 的 theme 属性名是 color 不是 backgroundColor
const timePickerThemeOverrides = computed(() => {
  // 保留全局配置依赖，确保配置变化时重算
  const _cfg = appearanceConfig.value.input
  const _dark = isDarkMode.value
  // 从组件自身 DOM 读取继承的 CSS 变量，以便支持 data-app-instance 级别的覆盖
  const el = timeRef.value
  const style = el ? getComputedStyle(el) : getComputedStyle(document.documentElement)
  const baseColor = style.getPropertyValue('--app-surface-card').trim()
  const bgOpacityRaw = style.getPropertyValue('--input-bg-opacity').trim()
  const bgOpacity = bgOpacityRaw ? parseFloat(bgOpacityRaw) / 100 : (_cfg.enabled ? _cfg.bg_opacity : 1)
  const radiusRaw = style.getPropertyValue('--input-border-radius').trim()
  const radius = radiusRaw || `${_cfg.enabled ? _cfg.border_radius : 8}px`
  const rgba = hexToRgba(baseColor, bgOpacity)
  return {
    peers: {
      Input: {
        color: rgba,
        colorFocus: rgba,
        border: '1px solid transparent',
        borderHover: '1px solid transparent',
        borderFocus: '1px solid transparent',
        borderRadius: radius
      }
    }
  }
})

function hexToRgba(hex: string, alpha: number): string {
  const match = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i)
  if (!match) return `rgba(30, 30, 46, ${alpha})`
  const r = parseInt(match[1], 16)
  const g = parseInt(match[2], 16)
  const b = parseInt(match[3], 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
</script>

<template>
  <div ref="timeRef" class="app-time-field">
    <div
      class="app-time-field__box"
      :class="{
        'is-focused': focused,
        'is-floated': isFloated,
        'is-disabled': disabled
      }"
    >
      <label
        v-if="label"
        class="app-time-field__label"
        :class="{ 'is-floated': isFloated, 'is-focused': focused }"
      >{{ label }}</label>

      <n-time-picker
        class="app-time-field__picker"
        :theme-overrides="timePickerThemeOverrides"
        :formatted-value="value"
        :value-format="valueFormat"
        :format="format"
        :size="size"
        :placeholder="showPlaceholder"
        :disabled="disabled"
        @update:formatted-value="handleUpdateFormattedValue"
        @focus="focused = true"
        @blur="(e: FocusEvent) => { focused = false; emit('blur', e) }"
      />
    </div>
  </div>
</template>

<style scoped>
.app-time-field {
  width: 100%;
}

.app-time-field__box {
  position: relative;
  height: var(--input-height, 56px);
  border: 1px solid var(--border-medium);
  border-radius: var(--input-border-radius, 8px);
  background: transparent;
  transition: border-color 0.2s;
}

.app-time-field__box:hover:not(.is-focused):not(.is-disabled) {
  border-color: var(--text-muted);
}

.app-time-field__box.is-focused {
  border-color: var(--n-primary-color);
}

.app-time-field__box.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-time-field__picker {
  width: 100%;
  height: 100%;
}

.app-time-field__picker :deep(.n-input) {
  height: 100% !important;
  border: none !important;
}

.app-time-field__picker :deep(.n-input .n-input-wrapper) {
  height: 100% !important;
  padding: 0 !important;
}

.app-time-field__picker :deep(.n-input .n-input__input) {
  height: 100% !important;
  display: flex !important;
  align-items: center !important;
  padding: 0 36px 0 16px !important;
  font-size: 16px;
  color: var(--text-primary);
}

.app-time-field__picker :deep(.n-input .n-input__input-el),
.app-time-field__picker :deep(.n-input .n-input__placeholder) {
  align-self: center !important;
  padding: 16px 0 !important;
  margin: 0 !important;
  height: auto !important;
  line-height: 24px !important;
}

.app-time-field__picker :deep(.n-input__border),
.app-time-field__picker :deep(.n-input__state-border) {
  display: none;
}

.app-time-field__picker :deep(.n-input .n-base-icon) {
  color: var(--text-muted);
}

.app-time-field__label {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 16px;
  pointer-events: none;
  transition: all 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 32px);
  padding: 0 4px;
  margin-left: -4px;
  background-color: var(--input-label-bg);
  line-height: 1;
  z-index: 1;
}

.app-time-field__label.is-floated {
  top: 0;
  transform: translateY(-50%) scale(0.85);
  color: var(--text-secondary);
}

.app-time-field__label.is-focused {
  color: var(--n-primary-color);
}
</style>
