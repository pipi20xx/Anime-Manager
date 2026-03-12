<script setup lang="ts">
import { NCard } from 'naive-ui'
import GuideContent from '@/docs/recognition-pipeline.md'
</script>

<template>
  <n-card bordered style="background: var(--app-surface-card)">
    <div class="md-content">
      <GuideContent />
    </div>
  </n-card>
</template>

<style scoped>
.md-content { line-height: 1.6; }
.md-content :deep(h1) { font-size: 1.5rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border-light); padding-bottom: 0.5rem; }
.md-content :deep(h2) { font-size: 1.3rem; margin-top: 1.5rem; margin-bottom: 1rem; color: var(--n-primary-color); }
.md-content :deep(h3) { font-size: 1.1rem; margin-top: 1.2rem; margin-bottom: 0.5rem; font-weight: bold; }
.md-content :deep(p) { margin-bottom: 1rem; }
.md-content :deep(ul) { padding-left: 1.5rem; margin-bottom: 1rem; }
.md-content :deep(li) { margin-bottom: 0.5rem; }
.md-content :deep(blockquote) { border-left: 4px solid var(--n-info-color); background: var(--color-info-bg); padding: 12px; border-radius: 4px; margin: 1rem 0; }
.md-content :deep(code) { background: var(--code-bg); padding: 2px 5px; border-radius: 4px; font-family: monospace; }
.md-content :deep(table) { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.md-content :deep(th), .md-content :deep(td) { border: 1px solid var(--border-light); padding: 8px; font-size: 0.9rem; }
.md-content :deep(th) { background: var(--table-header-bg); }
</style>