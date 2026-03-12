<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NImage, NModal } from 'naive-ui'
import GuideContent from '@/docs/settings-guide.md'

const previewImage = ref<string | null>(null)
const showPreview = ref(false)

const handleImageClick = (e: MouseEvent) => {
  const target = e.target as HTMLImageElement
  if (target.tagName === 'IMG') {
    previewImage.value = target.src
    showPreview.value = true
  }
}

onMounted(() => {
  const mdContent = document.querySelector('.md-content')
  if (mdContent) {
    mdContent.addEventListener('click', handleImageClick)
  }
})
</script>

<template>
  <n-card bordered style="background: var(--app-surface-card)">
    <div class="md-content">
      <GuideContent />
    </div>
  </n-card>
  
  <n-modal v-model:show="showPreview" preset="card" :style="{ width: '90vw', maxWidth: '1200px' }" :title="'图片预览'" :bordered="false" size="huge" :segmented="{ content: 'soft', footer: 'soft' }">
    <div class="preview-container">
      <n-image v-if="previewImage" :src="previewImage" object-fit="contain" />
    </div>
  </n-modal>
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

.md-content :deep(img) {
  max-width: 80%;
  height: auto;
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--transition-normal);
  box-shadow: 0 2px 8px var(--shadow-light);
}

.md-content :deep(img:hover) {
  transform: scale(1.02);
  box-shadow: 0 4px 12px var(--shadow-medium);
}

.preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.preview-container :deep(.n-image) {
  max-width: 100%;
  max-height: 80vh;
}
</style>
