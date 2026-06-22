<script setup lang="ts">
import { ref, computed } from 'vue'
import { NSelect, NIcon } from 'naive-ui'
import { ExpandMoreOutlined, ExpandLessOutlined } from '@vicons/material'

export interface SelectOption {
  label: string
  value: string | number | null
  disabled?: boolean
}

const props = withDefaults(defineProps<{
  value?: string | number | null | (string | number)[]
  label: string
  placeholder?: string
  options: SelectOption[]
  disabled?: boolean
  clearable?: boolean
  filterable?: boolean
  tag?: boolean
  multiple?: boolean
  remote?: boolean
  loading?: boolean
  maxTagCount?: 'responsive' | number
  fallbackOption?: false | ((value: string | number) => SelectOption)
  onSearch?: (query: string) => void
  onUpdateShow?: (show: boolean) => void
}>(), {
  clearable: false,
  filterable: false,
  tag: false,
  multiple: false,
  remote: false,
  loading: false
})

const emit = defineEmits<{
  (e: 'update:value', value: any): void
  (e: 'blur', event: FocusEvent): void
}>()

const focused = ref(false)
const showMenu = ref(false)

const handleUpdateShow = (show: boolean) => {
  showMenu.value = show
  props.onUpdateShow?.(show)
}

const hasValue = computed(() => {
  if (props.multiple && Array.isArray(props.value)) return props.value.length > 0
  return props.value !== '' && props.value != null
})

const isFloated = computed(() => focused.value || hasValue.value)
const showPlaceholder = computed(() =>
  (!props.label || focused.value || hasValue.value) ? props.placeholder : ''
)
</script>

<template>
  <div class="app-select-field">
    <div
      class="app-select-field__box"
      :class="{
        'is-focused': focused,
        'is-floated': isFloated,
        'is-disabled': disabled
      }"
    >
      <label
        v-if="label"
        class="app-select-field__label"
        :class="{ 'is-floated': isFloated, 'is-focused': focused }"
      >{{ label }}</label>

      <n-select
        class="app-select-field__select"
        :value="value"
        :options="options"
        :placeholder="showPlaceholder"
        :disabled="disabled"
        :clearable="clearable"
        :filterable="filterable"
        :tag="tag"
        :multiple="multiple"
        :remote="remote"
        :loading="loading"
        :max-tag-count="maxTagCount"
        :fallback-option="fallbackOption"
        :consistent-menu-width="false"
        @update:value="(val: any) => emit('update:value', val)"
        @focus="focused = true"
        @blur="(e: FocusEvent) => { focused = false; emit('blur', e) }"
        @search="(q: string) => onSearch?.(q)"
        @update:show="handleUpdateShow"
      />
      <div class="app-select-field__arrow">
        <n-icon size="20">
          <ExpandLessOutlined v-if="showMenu" />
          <ExpandMoreOutlined v-else />
        </n-icon>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-select-field {
  width: 100%;
}

.app-select-field__box {
  position: relative;
  height: 56px;
  border: 1px solid var(--border-medium);
  border-radius: 8px;
  background: transparent;
  transition: border-color 0.2s;
}

.app-select-field__box:hover:not(.is-focused):not(.is-disabled) {
  border-color: var(--text-muted);
}

.app-select-field__box.is-focused {
  border-color: var(--n-primary-color);
}

.app-select-field__box.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-select-field__select {
  width: 100%;
  height: 100%;
}

.app-select-field__select :deep(.n-base-selection) {
  height: 100% !important;
  border: none !important;
  background: transparent !important;
}

.app-select-field__select :deep(.n-base-selection-label) {
  height: 100% !important;
  display: flex;
  align-items: flex-start;
  padding: 18px 36px 0 16px !important;
  font-size: 16px;
  color: var(--text-primary);
}

.app-select-field__select :deep(.n-base-selection-label__input),
.app-select-field__select :deep(.n-base-selection-placeholder) {
  height: auto !important;
  line-height: 1.4 !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  margin-top: 0 !important;
}

.app-select-field__box:not(.is-floated) .app-select-field__select :deep(.n-base-selection-label) {
  padding-top: 4px !important;
  align-items: center !important;
}

.app-select-field__select :deep(.n-base-selection-tags) {
  padding: 18px 36px 6px 12px !important;
  align-items: center !important;
}

.app-select-field__select :deep(.n-base-selection__border) {
  display: none;
}

.app-select-field__select :deep(.n-base-selection__state-border) {
  display: none;
}

.app-select-field__select :deep(.n-base-suffix__arrow) {
  display: none !important;
}

.app-select-field__arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.app-select-field__label {
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
  background-color: var(--app-surface-card);
  line-height: 1;
  z-index: 1;
}

.app-select-field__label.is-floated {
  top: 0;
  transform: translateY(-50%) scale(0.85);
  color: var(--text-secondary);
}

.app-select-field__label.is-focused {
  color: var(--n-primary-color);
}
</style>
