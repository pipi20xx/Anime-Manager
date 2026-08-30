<script setup lang="ts">
/**
 * AiMarkdownContent — AI 消息 Markdown 渲染
 *
 * 流式输出时内容高频变化，按 96ms 节流重渲染，避免每个 delta 都全量解析 markdown
 */
import { ref, watch, onBeforeUnmount } from 'vue'
import { renderAiMarkdown } from '@/utils/aiMarkdown'

const props = defineProps<{ content: string; streaming?: boolean }>()

const STREAM_MARKDOWN_RENDER_INTERVAL = 96
const renderedHtml = ref('')
let lastRenderedAt = 0
let renderTimer: number | null = null

function renderNow() {
  lastRenderedAt = performance.now()
  if (renderTimer !== null) {
    window.clearTimeout(renderTimer)
    renderTimer = null
  }
  renderedHtml.value = renderAiMarkdown(props.content)
}

function scheduleRender() {
  const elapsed = performance.now() - lastRenderedAt
  if (elapsed >= STREAM_MARKDOWN_RENDER_INTERVAL) {
    renderNow()
    return
  }
  if (renderTimer !== null) return
  renderTimer = window.setTimeout(renderNow, STREAM_MARKDOWN_RENDER_INTERVAL - elapsed)
}

watch(() => props.content, scheduleRender, { immediate: true })

onBeforeUnmount(() => {
  if (renderTimer !== null) window.clearTimeout(renderTimer)
})
</script>

<template>
  <div class="ai-markdown" :class="{ 'ai-markdown--streaming': streaming }" v-html="renderedHtml"></div>
</template>

<style scoped>
.ai-markdown {
  font-size: 0.875rem;
  line-height: 1.65;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.ai-markdown :deep(p) {
  margin: 0 0 0.5em;
}

.ai-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.ai-markdown :deep(ul),
.ai-markdown :deep(ol) {
  margin: 0.25em 0 0.5em;
  padding-left: 1.4em;
}

.ai-markdown :deep(li) {
  margin: 0.15em 0;
}

.ai-markdown :deep(h1),
.ai-markdown :deep(h2),
.ai-markdown :deep(h3),
.ai-markdown :deep(h4) {
  font-size: 1em;
  font-weight: 700;
  margin: 0.6em 0 0.3em;
}

.ai-markdown :deep(blockquote) {
  margin: 0.4em 0;
  padding: 0.1em 0.8em;
  border-left: 3px solid rgba(var(--v-theme-primary), 0.5);
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.ai-markdown :deep(code:not(.hljs)) {
  padding: 0.1em 0.4em;
  border-radius: 4px;
  font-size: 0.85em;
  background: rgba(var(--v-theme-primary), 0.12);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.ai-markdown :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  font-size: 0.82rem;
  display: block;
  overflow-x: auto;
  max-width: 100%;
}

.ai-markdown :deep(th),
.ai-markdown :deep(td) {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
  padding: 4px 10px;
  text-align: left;
}

.ai-markdown :deep(th) {
  background: rgba(var(--v-theme-primary), 0.08);
  font-weight: 600;
}

.ai-markdown :deep(hr) {
  border: none;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  margin: 0.6em 0;
}

.ai-markdown :deep(a) {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}

.ai-markdown :deep(a:hover) {
  text-decoration: underline;
}

/* 代码块（fence 渲染器输出的 .ai-code-block） */
.ai-markdown :deep(.ai-code-block) {
  margin: 0.5em 0;
  border-radius: 8px;
  overflow: hidden;
  background: #0d1117;
}

.ai-markdown :deep(.ai-code-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.06);
}

.ai-markdown :deep(.ai-code-lang) {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.6);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.ai-markdown :deep(.ai-code-copy) {
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.72rem;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
}

.ai-markdown :deep(.ai-code-copy:hover) {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.ai-markdown :deep(.ai-code-block pre) {
  margin: 0;
  padding: 10px 12px;
  overflow-x: auto;
  max-height: 420px;
}

.ai-markdown :deep(.ai-code-block code) {
  font-size: 0.8rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: transparent;
  padding: 0;
}

/* 流式输出光标 */
.ai-markdown--streaming > :last-child::after {
  content: '▍';
  display: inline-block;
  margin-left: 2px;
  color: rgb(var(--v-theme-primary));
  animation: ai-cursor-blink 1s steps(2, start) infinite;
}

@keyframes ai-cursor-blink {
  to {
    visibility: hidden;
  }
}
</style>
