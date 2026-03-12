<script setup lang="ts">
interface Props {
  label: string
  value: string | number | null | undefined
  color?: string
}
defineProps<Props>()
</script>

<template>
  <div class="meta-box">
    <div class="label">{{ label }}</div>
    <div :class="['value', color]">
      {{ value ?? 'N/A' }}
    </div>
  </div>
</template>

<style scoped>
.meta-box {
  background: var(--app-surface-subtle);
  padding: 12px 16px;
  border-radius: var(--button-border-radius, 8px);
  border: 1px solid var(--app-border-light);
  transition: all var(--transition-normal);
}

.meta-box:hover {
  border-color: var(--app-border-medium);
  background: var(--app-surface-card);
}

.label {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.value {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.text-success { color: var(--n-primary-color); }
.text-info { color: var(--n-info-color); }
.text-warning { color: var(--n-warning-color); }
.text-error { color: var(--n-error-color); }
</style>