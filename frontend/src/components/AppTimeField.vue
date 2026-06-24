<script setup lang="ts">
import { ref, computed } from 'vue'
import { NTimePicker } from 'naive-ui'

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
</script>

<template>
  <div class="app-time-field">
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
  height: 56px;
  border: 1px solid var(--border-medium);
  border-radius: 8px;
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
  background: transparent !important;
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
  background-color: var(--app-surface-card);
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
