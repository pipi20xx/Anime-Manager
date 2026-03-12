<script setup lang="ts">
import { ref, watch } from 'vue'
import { 
  NModal, NButton, NScrollbar, NList, NListItem, NIcon, NSpace
} from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon,
  InsertDriveFileOutlined as FileIcon,
  ArrowUpwardOutlined as UpIcon
} from '@vicons/material'

const props = defineProps<{
  show: boolean
  initialPath?: string
  apiBase: string
  allowFiles?: boolean
}>()

const emit = defineEmits(['update:show', 'confirm'])

const currentPath = ref('/')
const selectedFile = ref<string | null>(null)
const items = ref<any[]>([])

const fetchFiles = async (path: string) => {
  try {
    const res = await fetch(`${props.apiBase}/api/files/list`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    })
    const data = await res.json()
    if (data.status === 'success') {
      currentPath.value = data.data.current_path
      items.value = data.data.items
      selectedFile.value = null // 切换目录清空选中文件
    }
  } catch (e) {}
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    fetchFiles(props.initialPath || '/')
  }
})

const goUp = () => {
  const parent = currentPath.value.split('/').slice(0, -1).join('/') || '/'
  fetchFiles(parent)
}

const handleItemClick = (item: any) => {
  if (item.is_dir) {
    fetchFiles(item.path)
  } else if (props.allowFiles) {
    selectedFile.value = item.path
  }
}

const handleConfirm = () => {
  const result = selectedFile.value || currentPath.value
  emit('confirm', result)
  emit('update:show', false)
}
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 500px" 
    :title="allowFiles ? '选择文件或目录' : '选择目录'"
  >
    <div class="picker-container">
      <n-space justify="space-between" align="center" class="mb-2">
        <n-button size="small" quaternary @click="goUp">
          <template #icon><n-icon><UpIcon /></n-icon></template>上级目录
        </n-button>
        <span class="path-text">{{ selectedFile || currentPath }}</span>
      </n-space>
      
      <n-scrollbar style="max-height: 350px" class="border-box">
        <n-list hoverable clickable>
          <n-list-item 
            v-for="item in items" 
            :key="item.path" 
            @click="handleItemClick(item)"
            :style="selectedFile === item.path ? 'background: var(--color-info-bg)' : ''"
          >
            <template #prefix>
              <n-icon :color="item.is_dir ? 'var(--n-primary-color)' : 'var(--text-muted)'">
                <component :is="item.is_dir ? FolderIcon : FileIcon" />
              </n-icon>
            </template>
            {{ item.name }}
          </n-list-item>
        </n-list>
      </n-scrollbar>
    </div>
    <template #action>
      <n-button type="primary" block @click="handleConfirm">
        {{ selectedFile ? '确认选择此文件' : '确认选择此目录' }}
      </n-button>
    </template>
  </n-modal>
</template>

<style scoped>
.path-text { font-size: 12px; font-family: monospace; color: var(--n-primary-color); word-break: break-all; max-width: 300px; text-align: right; }
.border-box { border: 1px solid var(--app-border-light); border-radius: 4px; margin-top: 8px; }
.mb-2 { margin-bottom: 8px; }
</style>