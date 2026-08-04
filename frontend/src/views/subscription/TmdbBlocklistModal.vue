<script setup lang="ts">
/**
 * TmdbBlocklistModal — TMDB 屏蔽列表弹窗
 */
import { ref, computed, watch, reactive } from 'vue'
import { subscriptionApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const blocklist = ref<any[]>([])
const loading = ref(false)
const blockForm = reactive({ tmdb_id: '', media_type: 'tv' })

watch(() => props.show, (v) => { if (v) fetchBlocklist() })

async function fetchBlocklist() {
  loading.value = true
  try {
    const data = await subscriptionApi.getTmdbBlocklist()
    blocklist.value = Array.isArray(data) ? data : (data?.items || data?.data || [])
  } catch { blocklist.value = [] }
  finally { loading.value = false }
}

async function addBlockItem() {
  if (!blockForm.tmdb_id) return
  try {
    await subscriptionApi.addTmdbBlocklistItem(blockForm)
    success('已添加')
    blockForm.tmdb_id = ''
    fetchBlocklist()
  } catch { showError('添加失败') }
}

async function removeBlockItem(id: number) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除此屏蔽条目吗？', confirmColor: 'error' })
  if (!ok) return
  try {
    await subscriptionApi.removeTmdbBlocklistItem(id)
    success('已删除')
    fetchBlocklist()
  } catch { showError('删除失败') }
}
</script>

<template>
  <v-dialog :model-value="show" max-width="720" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="error">mdi-shield-off-outline</v-icon>
        TMDB 屏蔽列表
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="$emit('update:show', false)" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-4">
          手动填入 TMDB ID 与类型，订阅源识别命中后直接标记已下载，跳过下载规则与追剧订阅。
        </div>

        <div class="d-flex ga-2 mb-4 add-btn-row align-center">
          <v-text-field v-model="blockForm.tmdb_id" label="TMDB ID" density="compact" hide-details variant="outlined" style="min-width: 120px" />
          <v-select v-model="blockForm.media_type" label="类型" :items="[{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]" density="compact" hide-details variant="outlined" style="min-width: 100px; max-width: 120px" />
          <v-btn color="primary" variant="flat" density="compact" @click="addBlockItem" prepend-icon="mdi-plus">添加</v-btn>
        </div>

        <v-skeleton-loader v-if="loading" type="card@3" />

        <v-row v-else-if="blocklist.length > 0" dense>
          <v-col v-for="item in blocklist" :key="item.id" cols="12" sm="6">
            <v-card variant="outlined" class="rounded-xl h-100 d-flex flex-column">
              <v-card-item class="pb-2">
                <div class="d-flex align-center ga-2">
                  <v-icon color="error" size="20">mdi-shield-off-outline</v-icon>
                  <v-card-title class="text-subtitle-1 font-weight-bold pa-0">TMDB {{ item.tmdb_id }}</v-card-title>
                </div>
              </v-card-item>
              <v-card-text class="pt-0 flex-grow-1">
                <div class="d-flex flex-wrap ga-2">
                  <v-chip size="x-small" variant="tonal" :color="item.media_type === 'tv' ? 'primary' : 'info'" label>
                    {{ item.media_type === 'tv' ? '剧集' : '电影' }}
                  </v-chip>
                </div>
                <div v-if="item.title" class="text-body-2 text-medium-emphasis mt-2 text-truncate">
                  <v-icon size="14" class="mr-1">mdi-text</v-icon>{{ item.title }}
                </div>
              </v-card-text>
              <v-card-actions class="pa-3 pt-0">
                <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="removeBlockItem(item.id)">删除</v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>

        <div v-else class="text-center pa-4">
          <div class="text-body-2 text-medium-emphasis">屏蔽列表为空</div>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 让添加按钮高度和 compact 输入框对齐 */
.add-btn-row .v-btn {
  block-size: 40px;
}
</style>
