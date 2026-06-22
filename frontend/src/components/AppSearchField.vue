<script setup lang="ts">
import { NIcon } from 'naive-ui'
import { SearchOutlined as SearchIcon, CloseOutlined } from '@vicons/material'

const props = withDefaults(defineProps<{
  value?: string
  placeholder?: string
  disabled?: boolean
  clearable?: boolean
  loading?: boolean
}>(), {
  value: '',
  clearable: true,
  loading: false
})

const emit = defineEmits<{
  (e: 'update:value', value: string): void
  (e: 'search', value: string): void
  (e: 'keyup', event: KeyboardEvent): void
  (e: 'blur', event: FocusEvent): void
}>()

const handleInput = (e: Event) => {
  emit('update:value', (e.target as HTMLInputElement).value)
}

const handleKeyup = (e: KeyboardEvent) => {
  emit('keyup', e)
  if (e.key === 'Enter') {
    emit('search', props.value)
  }
}

const clear = () => {
  emit('update:value', '')
  emit('search', '')
}

const triggerSearch = () => {
  emit('search', props.value)
}
</script>

<template>
  <div class="app-search-field">
    <div class="app-search-field__box">
      <div class="app-search-field__icon app-search-field__icon--left">
        <n-icon size="20"><SearchIcon /></n-icon>
      </div>
      <input
        class="app-search-field__input"
        type="text"
        :value="value"
        :placeholder="placeholder"
        :disabled="disabled"
        @input="handleInput"
        @keyup="handleKeyup"
        @blur="(e: FocusEvent) => emit('blur', e)"
      />
      <div
        v-if="clearable && value"
        class="app-search-field__icon app-search-field__icon--clear"
        @click="clear"
      >
        <n-icon size="16"><CloseOutlined /></n-icon>
      </div>
      <div class="app-search-field__search-btn" :class="{ 'is-loading': loading }" @click="triggerSearch">
        <n-icon size="18" class="app-search-field__search-icon"><SearchIcon /></n-icon>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-search-field {
  width: 100%;
}

.app-search-field__box {
  position: relative;
  height: 44px;
  border-radius: 22px;
  background: var(--n-input-color, rgba(128, 128, 128, 0.12));
  display: flex;
  align-items: center;
  padding: 0 6px 0 14px;
  transition: background 0.2s, box-shadow 0.2s;
}

.app-search-field__box:hover {
  background: var(--n-input-color-hover, rgba(128, 128, 128, 0.18));
}

.app-search-field__box:focus-within {
  background: var(--n-input-color-focus, rgba(128, 128, 128, 0.08));
  box-shadow: 0 0 0 2px var(--n-primary-color, #18a058) inset;
}

.app-search-field__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.app-search-field__icon--left {
  margin-right: 10px;
}

.app-search-field__icon--clear {
  margin-right: 6px;
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  transition: background 0.2s;
}

.app-search-field__icon--clear:hover {
  background: rgba(128, 128, 128, 0.15);
}

.app-search-field__search-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--n-primary-color, #18a058);
  color: #fff;
  flex-shrink: 0;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}

.app-search-field__search-btn:hover {
  opacity: 0.85;
}

.app-search-field__search-btn:active {
  transform: scale(0.95);
}

.app-search-field__search-btn.is-loading .app-search-field__search-icon {
  animation: app-search-spin 1s linear infinite;
}

@keyframes app-search-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.app-search-field__input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  background: transparent;
  outline: none;
  font-size: 15px;
  color: var(--text-primary);
}

.app-search-field__input::placeholder {
  color: var(--text-muted);
}
</style>
