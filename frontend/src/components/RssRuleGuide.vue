<script setup lang="ts">
import { NCard } from 'naive-ui'
import GuideContent from '@/docs/rss-rule-guide.md'
</script>

<template>
  <div class="rss-rule-guide">
    <GuideContent />
  </div>
</template>

<style scoped>
/* Scoped styles for the markdown content */
.rss-rule-guide {
  line-height: 1.6;
}

.rss-rule-guide :deep(h1) {
  font-size: 1.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--n-border-color);
  padding-bottom: 0.3em;
}

.rss-rule-guide :deep(h2) {
  font-size: 1.3rem;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  font-weight: 600;
}

.rss-rule-guide :deep(h3) {
  font-size: 1.1rem;
  margin-top: 1.2rem;
  margin-bottom: 0.8rem;
  font-weight: 600;
}

.rss-rule-guide :deep(p) {
  margin-bottom: 1rem;
}

.rss-rule-guide :deep(ul), .rss-rule-guide :deep(ol) {
  padding-left: 2rem;
  margin-bottom: 1rem;
}

.rss-rule-guide :deep(li) {
  margin-bottom: 0.5rem;
}

.rss-rule-guide :deep(blockquote) {
  margin: 1rem 0;
  padding: 0.5rem 1rem;
  color: var(--n-text-color-2);
  border-left: 4px solid var(--n-primary-color);
  background-color: var(--n-action-color);
  border-radius: 4px;
}

.rss-rule-guide :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  display: block;
  overflow-x: auto;
}

.rss-rule-guide :deep(th), .rss-rule-guide :deep(td) {
  border: 1px solid var(--n-border-color);
  padding: 0.5rem;
}

.rss-rule-guide :deep(th) {
  background-color: var(--n-table-header-color);
  font-weight: 600;
}

.rss-rule-guide :deep(code) {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  background-color: var(--n-code-color);
  border-radius: 3px;
  font-family: var(--code-font, monospace);
}

.rss-rule-guide :deep(pre) {
  padding: 1rem;
  overflow: auto;
  line-height: 1.45;
  background-color: var(--n-code-color);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.rss-rule-guide :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.rss-rule-guide :deep(a) {
  color: var(--n-primary-color);
  text-decoration: none;
}

.rss-rule-guide :deep(a:hover) {
  text-decoration: underline;
}

.rss-rule-guide :deep(hr) {
  height: 0.25em;
  padding: 0;
  margin: 2rem 0;
  background-color: var(--n-border-color);
  border: 0;
}
</style>