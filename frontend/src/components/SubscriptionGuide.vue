<script setup lang="ts">
import { NCard } from 'naive-ui'
import GuideContent from '@/docs/subscription-guide.md'
</script>

<template>
  <n-card bordered>
    <div class="md-content">
      <GuideContent />
    </div>
  </n-card>
</template>

<style scoped>
.md-content {
  line-height: 1.6;
}
.md-content :deep(h3) { font-size: 1.2rem; font-weight: bold; margin: 1.5rem 0 1rem; color: var(--n-text-color-1); }
.md-content :deep(p) { margin-bottom: 1rem; color: var(--n-text-color-2); }
.md-content :deep(ul) { padding-left: 1.5rem; margin-bottom: 1rem; }
.md-content :deep(li) { margin-bottom: 0.5rem; }
.md-content :deep(blockquote) { border-left: 4px solid var(--n-primary-color); padding-left: 1rem; margin: 1rem 0; color: var(--n-text-color-3); background: var(--n-action-color); padding: 8px 12px; border-radius: 4px; }
.md-content :deep(table) { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.md-content :deep(th), .md-content :deep(td) { border: 1px solid var(--n-border-color); padding: 8px; font-size: 0.9rem; }
.md-content :deep(th) { background: var(--n-table-header-color); }
.md-content :deep(code) { background: var(--n-code-color); padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 0.9em; }
</style>