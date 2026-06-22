<script setup lang="ts">
import { ref, computed } from 'vue'
import { NIcon } from 'naive-ui'
import {
  VisibilityOutlined as EyeOpenIcon,
  VisibilityOffOutlined as EyeClosedIcon
} from '@vicons/material'

const props = withDefaults(defineProps<{
  value: string | number | null
  label: string
  placeholder?: string
  type?: 'text' | 'password' | 'textarea' | 'number'
  hint?: string
  prefixIcon?: any
  disabled?: boolean
  readonly?: boolean
  maxlength?: string | number
  autofocus?: boolean
  autosize?: boolean | { minRows?: number; maxRows?: number }
  min?: string | number
  max?: string | number
  step?: string | number
}>(), {
  type: 'text'
})

const emit = defineEmits<{
  (e: 'update:value', value: string | number | null): void
  (e: 'keyup', event: KeyboardEvent): void
  (e: 'blur', event: FocusEvent): void
}>()

const focused = ref(false)
const showPassword = ref(false)

const isPassword = computed(() => props.type === 'password')
const isTextarea = computed(() => props.type === 'textarea')
const isNumber = computed(() => props.type === 'number')
const inputType = computed(() => {
  if (isPassword.value) return showPassword.value ? 'text' : 'password'
  if (isNumber.value) return 'number'
  return props.type
})
const hasValue = computed(() => props.value !== '' && props.value != null)
const isFloated = computed(() => focused.value || hasValue.value || isTextarea.value)
const showPlaceholder = computed(() => (!props.label || focused.value || hasValue.value) ? props.placeholder : '')

const textRows = computed(() => {
  if (!isTextarea.value) return undefined
  if (typeof props.autosize === 'object' && props.autosize?.minRows) return props.autosize.minRows
  return 2
})

const handleInput = (e: Event) => {
  const raw = (e.target as HTMLInputElement).value
  if (isNumber.value) {
    emit('update:value', raw === '' ? null : Number(raw))
  } else {
    emit('update:value', raw)
  }
}
</script>

<template>
  <div class="app-text-field">
    <div
      class="app-text-field__box"
      :class="{
        'is-focused': focused,
        'is-floated': isFloated,
        'is-disabled': disabled,
        'is-textarea': isTextarea,
        'has-prefix': !!prefixIcon || !!$slots.prefix,
        'has-suffix': !!$slots.suffix || isPassword
      }"
    >
      <div v-if="$slots.prefix" class="app-text-field__prefix app-text-field__prefix--custom">
        <slot name="prefix" />
      </div>
      <div v-else-if="prefixIcon" class="app-text-field__prefix">
        <n-icon size="20"><component :is="prefixIcon" /></n-icon>
      </div>

      <label
        v-if="label"
        class="app-text-field__label"
        :class="{ 'is-floated': isFloated, 'is-focused': focused, 'is-textarea': isTextarea }"
      >{{ label }}</label>

      <template v-if="isTextarea">
        <textarea
          class="app-text-field__input app-text-field__input--textarea"
          :rows="textRows"
          :value="value"
          :placeholder="showPlaceholder"
          :disabled="disabled"
          :readonly="readonly"
          @input="handleInput"
          @focus="focused = true"
          @blur="(e: FocusEvent) => { focused = false; emit('blur', e) }"
          @keyup="(e: KeyboardEvent) => emit('keyup', e)"
        />
      </template>
      <input
        v-else
        :type="inputType"
        class="app-text-field__input"
        :value="value"
        :placeholder="showPlaceholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxlength"
        :autofocus="autofocus"
        :min="min"
        :max="max"
        :step="step"
        @input="handleInput"
        @focus="focused = true"
        @blur="(e: FocusEvent) => { focused = false; emit('blur', e) }"
        @keyup="(e: KeyboardEvent) => emit('keyup', e)"
      />

      <div
        v-if="$slots.suffix"
        class="app-text-field__suffix app-text-field__suffix--custom"
      >
        <slot name="suffix" />
      </div>
      <div
        v-else-if="isPassword"
        class="app-text-field__suffix"
        @click="showPassword = !showPassword"
      >
        <n-icon size="20"><component :is="showPassword ? EyeClosedIcon : EyeOpenIcon" /></n-icon>
      </div>
    </div>

    <div v-if="hint || $slots.hint" class="app-text-field__hint">
      <slot name="hint">{{ hint }}</slot>
    </div>
  </div>
</template>

<style scoped>
.app-text-field {
  width: 100%;
}

.app-text-field__box {
  position: relative;
  height: 56px;
  border: 1px solid var(--border-medium);
  border-radius: 8px;
  background: transparent;
  transition: border-color 0.2s;
  display: flex;
  align-items: center;
}

.app-text-field__box.is-textarea {
  height: auto;
  min-height: 72px;
  align-items: flex-start;
}

.app-text-field__box:hover:not(.is-focused):not(.is-disabled) {
  border-color: var(--text-muted);
}

.app-text-field__box.is-focused {
  border-color: var(--n-primary-color);
}

.app-text-field__box.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.app-text-field__input {
  width: 100%;
  height: 100%;
  padding: 0 16px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.4;
  outline: none;
  border-radius: 8px;
}

.app-text-field__input::-webkit-outer-spin-button,
.app-text-field__input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.app-text-field__input[type='number'] {
  -moz-appearance: textfield;
}

.app-text-field__input--textarea {
  height: auto;
  min-height: 72px;
  padding: 20px 16px 8px;
  resize: vertical;
}

.app-text-field__box.has-prefix .app-text-field__input {
  padding-left: 44px;
}

.app-text-field__box.has-prefix .app-text-field__input--textarea {
  padding-left: 44px;
}

.app-text-field__box.has-suffix .app-text-field__input {
  padding-right: 44px;
}

.app-text-field__box.has-suffix .app-text-field__input--textarea {
  padding-right: 44px;
}

.app-text-field__label {
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
}

.app-text-field__box.has-prefix .app-text-field__label {
  left: 44px;
  max-width: calc(100% - 60px);
}

.app-text-field__label.is-floated {
  top: 0;
  transform: translateY(-50%) scale(0.85);
  color: var(--text-secondary);
}

.app-text-field__label.is-focused {
  color: var(--n-primary-color);
}

.app-text-field__prefix,
.app-text-field__suffix {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.app-text-field__prefix {
  left: 12px;
  pointer-events: none;
}

.app-text-field__prefix--custom {
  pointer-events: auto;
}

.app-text-field__suffix {
  right: 12px;
  cursor: pointer;
}

.app-text-field__suffix--custom {
  cursor: default;
}

.app-text-field__hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-muted);
}
</style>
