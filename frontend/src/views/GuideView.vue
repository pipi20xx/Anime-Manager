<script setup lang="ts">
/**
 * GuideView — 规则使用说明
 *
 * 直接加载 src/docs/ 下的 Markdown 文档，用 marked 运行时渲染。
 * 标签页与旧前端完全一致。
 */
import { ref, computed, watch } from 'vue'
import { marked } from 'marked'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'

defineOptions({ name: 'GuideView' })

// 导入 Markdown 原始文本 (?raw 后缀由 Vite 内置支持)
import settingsMd from '@/docs/settings-guide.md?raw'
import pipelineMd from '@/docs/recognition-pipeline.md?raw'
import recognitionMd from '@/docs/recognition-rules.md?raw'
import privilegedMd from '@/docs/privileged-rules.md?raw'
import renderMd from '@/docs/render-rules.md?raw'
import rssMd from '@/docs/rss-rule-guide.md?raw'
import subscriptionMd from '@/docs/subscription-guide.md?raw'
import strmMd from '@/docs/strm-guide.md?raw'
import dataCenterMd from '@/docs/data-center-guide.md?raw'

// 预加载 docs 目录下所有图片，将相对路径映射为 Vite 解析后的 URL
// 解决 Markdown 中 ./xxx.png 相对路径在浏览器中 404 的问题
const docImages = import.meta.glob('@/docs/*.{png,jpg,jpeg,gif,svg,webp}', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

// 构建 文件名 -> URL 映射
const imageMap: Record<string, string> = {}
for (const [path, url] of Object.entries(docImages)) {
  const filename = path.split('/').pop() || ''
  if (filename) imageMap[filename] = url
}

/**
 * 将 Markdown 中的相对图片路径替换为 Vite 解析后的 URL
 * 支持 ![alt](./xxx.png) 和 ![alt](xxx.png) 两种写法
 */
function resolveImagePaths(md: string): string {
  return md.replace(/!\[([^\]]*)\]\((\.\/)?([^)]+)\)/g, (match, alt, _prefix, filename) => {
    const url = imageMap[filename]
    return url ? `![${alt}](${url})` : match
  })
}

const activeTab = ref('settings')

const tabs = [
  { value: 'settings', label: '设置说明', icon: 'mdi-cog-outline', md: settingsMd },
  { value: 'pipeline', label: '全链路识别流水线', icon: 'mdi-pipe', md: pipelineMd },
  { value: 'recognition', label: '自定义识别词 (预处理)', icon: 'mdi-filter-outline', md: recognitionMd },
  { value: 'privileged', label: '自定义特权规则 (优先提取)', icon: 'mdi-crown-outline', md: privilegedMd },
  { value: 'render', label: '自定义渲染词 (后处理)', icon: 'mdi-palette-outline', md: renderMd },
  { value: 'rss', label: '下载规则配置 (RSS)', icon: 'mdi-rss', md: rssMd },
  { value: 'subscription', label: '追剧订阅配置 (TMDB)', icon: 'mdi-television-classic', md: subscriptionMd },
  { value: 'strm', label: '虚拟库 (STRM)', icon: 'mdi-link-variant', md: strmMd },
  { value: 'datacenter', label: '数据中心架构', icon: 'mdi-database-outline', md: dataCenterMd },
]

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const currentTab = computed(() => tabs.find(t => t.value === activeTab.value))

const renderedHtml = computed(() => {
  if (!currentTab.value) return ''
  return marked.parse(resolveImagePaths(currentTab.value.md)) as string
})

// 切换标签页时滚动到顶部
watch(activeTab, () => {
  const el = document.querySelector('.md-content-wrapper')
  if (el) el.scrollTop = 0
})

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: tabs.map(t => ({ title: t.label, icon: t.icon, tab: t.value })),
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <v-window-item v-for="tab in tabs" :key="tab.value" :value="tab.value">
        <v-card class="glass-card" rounded="xl">
          <v-card-text class="pa-6">
            <div class="md-content" v-html="renderedHtml" />
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>

<style scoped>
.md-content {
  line-height: 1.8;
  max-width: 100%;
  overflow-x: auto;
}

/* 标题样式 */
.md-content :deep(h1) {
  font-size: 1.6rem;
  font-weight: 800;
  margin-bottom: 1rem;
  border-bottom: 2px solid rgba(var(--v-theme-on-surface), 0.12);
  padding-bottom: 0.5rem;
}

.md-content :deep(h2) {
  font-size: 1.35rem;
  font-weight: 700;
  margin-top: 2rem;
  margin-bottom: 1rem;
  color: rgb(var(--v-theme-on-surface));
}

.md-content :deep(h3) {
  font-size: 1.15rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

.md-content :deep(h4) {
  font-size: 1.05rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: rgb(var(--v-theme-on-surface));
}

/* 段落 */
.md-content :deep(p) {
  margin-bottom: 1rem;
}

/* 列表 */
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 1.8rem;
  margin-bottom: 1rem;
}

.md-content :deep(li) {
  margin-bottom: 0.4rem;
}

/* 引用块 */
.md-content :deep(blockquote) {
  border-left: 4px solid rgba(var(--v-theme-on-surface), 0.2);
  background: rgba(var(--v-theme-on-surface), 0.04);
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
  margin: 1rem 0;
}

.md-content :deep(blockquote p) {
  margin-bottom: 0.3rem;
}

.md-content :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

/* 表格 */
.md-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  display: block;
  overflow-x: auto;
}

.md-content :deep(th),
.md-content :deep(td) {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  padding: 8px 12px;
  font-size: 0.875rem;
  text-align: left;
}

.md-content :deep(th) {
  background: rgba(var(--v-theme-on-surface), 0.06);
  font-weight: 700;
  white-space: nowrap;
}

.md-content :deep(tr:nth-child(even)) {
  background: rgba(var(--v-theme-on-surface), 0.02);
}

/* 行内代码 */
.md-content :deep(code) {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgb(var(--v-theme-on-surface));
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.85em;
}

/* 代码块 */
.md-content :deep(pre) {
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1rem 0;
  line-height: 1.5;
}

.md-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: 0.85rem;
}

/* 链接 */
.md-content :deep(a) {
  color: rgb(var(--v-theme-info));
  text-decoration: underline;
}

.md-content :deep(a:hover) {
  text-decoration: underline;
}

/* 分割线 */
.md-content :deep(hr) {
  border: none;
  height: 1px;
  background: rgba(var(--v-theme-on-surface), 0.12);
  margin: 2rem 0;
}

/* 粗体 */
.md-content :deep(strong) {
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
}

/* 图片 */
.md-content :deep(img) {
  max-width: 80%;
  height: auto;
  border-radius: 8px;
  margin: 1rem 0;
}
</style>
