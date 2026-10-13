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
  <div class="markdown-body markdown-body--chat" :class="{ 'md-streaming': streaming }" v-html="renderedHtml"></div>
</template>
