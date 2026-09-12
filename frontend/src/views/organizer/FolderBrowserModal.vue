<script setup lang="ts">
/**
 * FolderBrowserModal — 目录/文件浏览选择弹窗
 * 按 via 切换数据源：local（POST /api/files/list）| cd2（GET /api/cd2/files）
 * mode='dir' 仅选目录；mode='file' 可选文件（目录仍可进入）。
 */
import { computed, ref, watch } from 'vue'
import { organizerApi, cd2Api } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'FolderBrowserModal' })

const props = defineProps<{
  modelValue: boolean
  via: 'local' | 'cd2'
  title?: string
  mode?: 'dir' | 'file'
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  select: [path: string]
}>()

const { error: showError } = useNotification()

const loading = ref(false)
const currentPath = ref('/')
const dirs = ref<any[]>([])
const files = ref<any[]>([])
const parentPath = ref('')
const selectedFile = ref('')

const isFileMode = computed(() => props.mode === 'file')

const breadcrumbs = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  const crumbs = [{ name: props.via === 'cd2' ? '根目录' : '/', path: '/' }]
  let acc = ''
  for (const p of parts) {
    acc += `/${p}`
    crumbs.push({ name: p, path: acc })
  }
  return crumbs
})

const load = async () => {
  loading.value = true
  selectedFile.value = ''
  try {
    if (props.via === 'cd2') {
      const res = await cd2Api.browseFiles(currentPath.value)
      dirs.value = (res.entries || []).filter((e: any) => e.is_dir)
      files.value = isFileMode.value ? (res.entries || []).filter((e: any) => !e.is_dir) : []
      parentPath.value = ''
    } else {
      const res = await organizerApi.listFiles({ path: currentPath.value })
      const data = res?.data ?? res
      dirs.value = (data.items || []).filter((i: any) => i.is_dir)
      files.value = isFileMode.value ? (data.items || []).filter((i: any) => !i.is_dir) : []
      parentPath.value = data.parent_path || ''
    }
  } catch (e: any) {
    const msg = e?.message || ''
    if (msg.includes('403') || msg.toLowerCase().includes('permission')) {
      showError('该路径不在允许浏览的范围内 (organizer_allowed_roots)')
    } else {
      showError(msg || '列出目录失败')
    }
  } finally {
    loading.value = false
  }
}

const navigate = (path: string) => {
  currentPath.value = path
  load()
}

const goUp = () => {
  if (props.via === 'local' && parentPath.value) {
    navigate(parentPath.value)
  } else {
    const parts = currentPath.value.split('/').filter(Boolean)
    parts.pop()
    navigate('/' + parts.join('/'))
  }
}

const pickFile = (path: string) => {
  selectedFile.value = selectedFile.value === path ? '' : path
}

const choose = () => {
  emit('select', isFileMode.value && selectedFile.value ? selectedFile.value : currentPath.value)
  emit('update:modelValue', false)
}

// 每次打开时按 via 重置起始路径
watch(() => props.modelValue, (open) => {
  if (open) {
    currentPath.value = props.via === 'cd2' ? '/' : '/'
    load()
  }
})
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    max-width="600"
    scrollable
  >
    <v-card class="glass-card">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-folder-search-outline</v-icon>
        {{ title || (via === 'cd2' ? '浏览 CD2 云盘目录' : '浏览本地目录') }}
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" @click="emit('update:modelValue', false)" />
      </v-card-title>
      <v-divider />

      <!-- 面包屑导航 -->
      <v-card-text class="pb-2">
        <div class="d-flex align-center flex-wrap gap-1">
          <template v-for="(crumb, i) in breadcrumbs" :key="crumb.path">
            <v-btn
              variant="text"
              size="small"
              density="compact"
              class="text-none px-1"
              :color="i === breadcrumbs.length - 1 ? 'primary' : undefined"
              @click="navigate(crumb.path)"
            >
              {{ crumb.name }}
            </v-btn>
            <v-icon v-if="i < breadcrumbs.length - 1" size="x-small">mdi-chevron-right</v-icon>
          </template>
          <v-spacer />
          <v-btn
            icon="mdi-arrow-up"
            size="small"
            variant="text"
            :disabled="currentPath === '/'"
            title="上一级"
            @click="goUp"
          />
        </div>
      </v-card-text>
      <v-divider />

      <!-- 列表 -->
      <v-card-text class="pa-0" style="min-height: 240px; max-height: 45vh; overflow-y: auto">
        <div v-if="loading" class="d-flex justify-center pa-8">
          <v-progress-circular indeterminate color="primary" />
        </div>
        <div v-else-if="!dirs.length && !files.length" class="text-center text-medium-emphasis pa-8">
          {{ isFileMode ? '目录为空' : '没有子目录' }}
        </div>
        <v-list v-else class="py-0">
          <v-list-item
            v-for="d in dirs"
            :key="d.path"
            class="px-2"
            @click="navigate(d.path)"
          >
            <template #prepend>
              <v-icon color="amber-darken-2">mdi-folder</v-icon>
            </template>
            <v-list-item-title class="text-body-2">{{ d.name }}</v-list-item-title>
          </v-list-item>
          <template v-if="isFileMode">
            <v-list-item
              v-for="f in files"
              :key="f.path"
              class="px-2"
              :active="selectedFile === f.path"
              @click="pickFile(f.path)"
            >
              <template #prepend>
                <v-icon :color="selectedFile === f.path ? 'primary' : 'grey-lighten-1'">
                  {{ selectedFile === f.path ? 'mdi-check-circle' : 'mdi-file-outline' }}
                </v-icon>
              </template>
              <v-list-item-title class="text-body-2">{{ f.name }}</v-list-item-title>
            </v-list-item>
          </template>
        </v-list>
      </v-card-text>

      <v-divider />
      <v-card-text class="py-2 text-caption text-medium-emphasis text-truncate">
        {{ selectedFile ? `已选文件: ${selectedFile}` : `当前: ${currentPath}` }}
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn color="primary" prepend-icon="mdi-check" @click="choose">
          {{ isFileMode && selectedFile ? '选择该文件' : '选择当前目录' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

