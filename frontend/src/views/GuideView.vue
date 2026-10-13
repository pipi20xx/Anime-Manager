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
            <div class="markdown-body markdown-body--guide" v-html="renderedHtml" />
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>
