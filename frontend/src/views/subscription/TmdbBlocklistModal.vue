<script setup lang="ts">
/**
 * TmdbBlocklistModal — TMDB 屏蔽列表弹窗
 * 列表弹窗 + 独立的添加/编辑表单弹窗（与订阅源编辑弹窗同一交互模式）
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

// ── 添加/编辑表单弹窗（共用一个 dialog） ──
const showFormModal = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
// 编辑时保留表单未覆盖的条件键（如经 API 设置的 audio_encode/subtitle 等）
const editingExtra = ref<Record<string, string>>({})
const blockForm = reactive({ tmdb_id: '', media_type: 'all', team: '', resolution: '', source: '', video_encode: '' })

// 锚定作品时必须二选一类型；留空 TMDB ID 的全局条件条目额外支持"全部"
const typeOptions = computed(() =>
  blockForm.tmdb_id.trim()
    ? [{ title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]
    : [{ title: '全部', value: 'all' }, { title: '剧集', value: 'tv' }, { title: '电影', value: 'movie' }]
)
watch(() => blockForm.tmdb_id, (v) => {
  if (v.trim() && blockForm.media_type === 'all') blockForm.media_type = 'tv'
})

function mediaTypeLabel(t: string) {
  return t === 'tv' ? '剧集' : t === 'movie' ? '电影' : '全部'
}

// 规格条件字段（键与 field_match.FIELD_MATCH_STRATEGY 对应），卡片信息区固定全部展示
const CONDITION_FIELDS = [
  { key: 'team', label: '制作组' },
  { key: 'resolution', label: '分辨率' },
  { key: 'source', label: '来源' },
  { key: 'video_encode', label: '视频编码' },
  { key: 'audio_encode', label: '音频编码' },
  { key: 'subtitle', label: '字幕' },
  { key: 'platform', label: '平台' },
  { key: 'video_effect', label: '特效' },
]

function getConditionLines(item: any): { label: string; value: string; unset: boolean }[] {
  const c = item.conditions || {}
  return CONDITION_FIELDS.map(({ key, label }) => {
    const val = c[key] || ''
    return { label, value: val || '无', unset: !val }
  })
}

const FORM_CONDITION_KEYS = ['team', 'resolution', 'source', 'video_encode']

function buildConditions(): Record<string, string> {
  const c: Record<string, string> = { ...editingExtra.value }
  for (const k of FORM_CONDITION_KEYS) {
    const v = (blockForm as any)[k]?.trim()
    if (v) c[k] = v
    else delete c[k]
  }
  return c
}

function resetForm() {
  blockForm.tmdb_id = ''
  blockForm.media_type = 'all'
  blockForm.team = ''
  blockForm.resolution = ''
  blockForm.source = ''
  blockForm.video_encode = ''
}

function openAdd() {
  editingId.value = null
  editingExtra.value = {}
  resetForm()
  showFormModal.value = true
}

function openEdit(item: any) {
  editingId.value = item.id
  blockForm.tmdb_id = item.tmdb_id || ''
  blockForm.media_type = item.media_type || 'tv'
  const c = item.conditions || {}
  blockForm.team = c.team || ''
  blockForm.resolution = c.resolution || ''
  blockForm.source = c.source || ''
  blockForm.video_encode = c.video_encode || ''
  editingExtra.value = Object.fromEntries(
    Object.entries(c).filter(([k]) => !FORM_CONDITION_KEYS.includes(k))
  ) as Record<string, string>
  showFormModal.value = true
}

function closeForm() {
  showFormModal.value = false
  editingId.value = null
  editingExtra.value = {}
  resetForm()
}

function errDetail(e: any, fallback: string) {
  return e?.response?.data?.detail || fallback
}

watch(() => props.show, (v) => { if (v) fetchBlocklist(); else closeForm() })

async function fetchBlocklist() {
  loading.value = true
  try {
    const data = await subscriptionApi.getTmdbBlocklist()
    blocklist.value = Array.isArray(data) ? data : (data?.items || data?.data || [])
  } catch { blocklist.value = [] }
  finally { loading.value = false }
}

async function submitForm() {
  const tmdbId = blockForm.tmdb_id.trim()
  const conditions = buildConditions()
  if (!tmdbId && Object.keys(conditions).length === 0) {
    showError('留空 TMDB ID 时需至少填写一个规格条件（如制作组）')
    return
  }
  const payload = { tmdb_id: tmdbId, media_type: blockForm.media_type, conditions }
  submitting.value = true
  try {
    if (editingId.value != null) {
      await subscriptionApi.updateTmdbBlocklistItem(editingId.value, payload)
      success('已保存')
    } else {
      await subscriptionApi.addTmdbBlocklistItem(payload)
      success('已添加')
    }
    closeForm()
    fetchBlocklist()
  } catch (e) {
    showError(errDetail(e, editingId.value != null ? '保存失败' : '添加失败'))
  } finally {
    submitting.value = false
  }
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
  <!-- 列表弹窗 -->
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
          命中屏蔽条目的资源，识别后直接标记已下载，跳过下载规则与追剧订阅。
          支持三种粒度：整部作品、指定作品内满足规格条件的资源、以及不锚定作品的全局条件屏蔽（如屏蔽某制作组的全部发布）。
        </div>

        <div class="d-flex mb-4">
          <v-spacer />
          <v-btn variant="tonal" color="error" prepend-icon="mdi-plus" @click="openAdd">添加屏蔽</v-btn>
        </div>

        <v-skeleton-loader v-if="loading" type="card@3" />

        <v-row v-else-if="blocklist.length > 0" density="compact">
          <v-col v-for="item in blocklist" :key="item.id" cols="12" sm="6">
            <v-card class="glass-card manage-card">
              <!-- 标题行 -->
              <div class="manage-card__header">
                <div class="d-flex align-center ga-2 manage-card__title">
                  <v-icon color="error" size="18">mdi-shield-off-outline</v-icon>
                  <span class="text-truncate">{{ item.resolved_title || item.title || (item.tmdb_id ? `TMDB ${item.tmdb_id}` : '全局条件屏蔽') }}</span>
                </div>
                <v-chip size="x-small" variant="tonal" :color="item.media_type === 'tv' ? 'primary' : item.media_type === 'movie' ? 'info' : 'deep-purple'" label class="manage-card__badge">
                  {{ mediaTypeLabel(item.media_type) }}
                </v-chip>
              </div>

              <!-- 信息区：固定 8 个规格条件，未设置显示「无」 -->
              <div class="manage-card__body">
                <div class="manage-card__info" v-for="line in getConditionLines(item)" :key="line.label">
                  <span class="manage-card__info-label">{{ line.label }}</span>
                  <span class="manage-card__info-value" :class="{ 'text-medium-emphasis': line.unset }" :title="line.value">{{ line.value }}</span>
                </div>

                <div class="manage-card__tags">
                  <v-chip v-if="item.tmdb_id" size="x-small" variant="tonal" color="secondary" label>
                    TMDB {{ item.tmdb_id }}
                  </v-chip>
                  <v-chip v-if="!item.conditions || !Object.keys(item.conditions).length" size="x-small" variant="tonal" color="error" label>
                    整部作品
                  </v-chip>
                </div>
              </div>

              <v-divider />
              <v-card-actions class="manage-card__actions">
                <v-spacer />
                <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-pencil-outline" @click="openEdit(item)">编辑</v-btn>
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

  <!-- 添加/编辑表单弹窗 -->
  <v-dialog v-model="showFormModal" max-width="480" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="error">mdi-shield-off-outline</v-icon>
        {{ editingId != null ? '编辑屏蔽条目' : '添加屏蔽条目' }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="closeForm" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field v-model="blockForm.tmdb_id" label="TMDB ID（可留空）" placeholder="留空 = 按条件全局屏蔽" variant="outlined" density="compact" class="mb-3" />
        <v-select v-model="blockForm.media_type" label="类型" :items="typeOptions" variant="outlined" density="compact" class="mb-3" />

        <div class="text-subtitle-2 font-weight-medium mb-2">规格条件（可选，多条需同时满足）</div>
        <v-text-field v-model="blockForm.team" label="制作组" placeholder="如 LoliHouse,Subz" variant="outlined" density="compact" class="mb-3" />
        <v-text-field v-model="blockForm.resolution" label="分辨率" placeholder="如 2160p,1080p" variant="outlined" density="compact" class="mb-3" />
        <v-text-field v-model="blockForm.source" label="来源" placeholder="如 Web,Blu-ray" variant="outlined" density="compact" class="mb-3" />
        <v-text-field v-model="blockForm.video_encode" label="视频编码" placeholder="如 H265,H264" variant="outlined" density="compact" class="mb-2" />

        <div class="text-caption text-medium-emphasis">
          条件值支持逗号分隔多个；全部留空 = 屏蔽整部作品（订阅同步标记已下载）；
          留空 TMDB ID 时至少填写一个条件，即全局条件屏蔽。
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="closeForm">取消</v-btn>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" :loading="submitting" @click="submitForm">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
