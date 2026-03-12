<script setup lang="ts">
import { NCard } from 'naive-ui'
import GuideContent from '@/docs/strm-guide.md'
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
.md-content :deep(h3) { font-size: 1.4rem; margin-bottom: 1rem; border-bottom: 1px solid var(--n-border-color); padding-bottom: 0.5rem; }
.md-content :deep(h4) { font-size: 1.1rem; margin-top: 1.5rem; margin-bottom: 0.8rem; color: var(--n-primary-color); }
.md-content :deep(blockquote) { border-left: 4px solid var(--n-warning-color); background: var(--color-warning-bg); padding: 12px; border-radius: 4px; margin: 1rem 0; }
.md-content :deep(ul) { padding-left: 1.5rem; margin-bottom: 1rem; }
.md-content :deep(li) { margin-bottom: 0.5rem; }
.md-content :deep(code) { background: var(--n-code-color); padding: 2px 5px; border-radius: 4px; font-family: monospace; }
</style>
