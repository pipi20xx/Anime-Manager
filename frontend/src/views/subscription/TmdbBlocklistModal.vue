<script setup lang="ts">
/**
 * TmdbBlocklistModal — TMDB 屏蔽列表弹窗
 * 列表弹窗 + 独立的添加/编辑表单弹窗（与订阅源编辑弹窗同一交互模式）
 */
import { ref, computed, watch, reactive } from 'vue'
import { subscriptionApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { useMappingCache } from '@/composables/useDataCenter'
import { DialogTitle, FieldConditionSelect, ArchiveCriteriaFields } from '@/components/common'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
}>()

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()
const { translateIds, fetchMappingCache } = useMappingCache()

const blocklist = ref<any[]>([])
const loading = ref(false)

// ── 添加/编辑表单弹窗（共用一个 dialog） ──
const showFormModal = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const blockForm = reactive({ tmdb_id: '', media_type: 'all', team: '', resolution: '', source: '', video_encode: '', audio_encode: '', subtitle: '', platform: '', video_effect: '' })
// 档案级条件（流派/公司/关键词等，键同二级分类规则 criteria），单独由 ArchiveCriteriaFields 维护
const archiveCriteria = ref<Record<string, any>>({})

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

// 匹配条件字段：与订阅表单（SubEditModal）同一套字段与措辞，键同 field_match.FIELD_MATCH_STRATEGY
const CONDITION_FIELDS = [
  { key: 'resolution', label: '分辨率' },
  { key: 'team', label: '制作组' },
  { key: 'source', label: '介质来源' },
  { key: 'video_encode', label: '视频编码' },
  { key: 'audio_encode', label: '音频编码' },
  { key: 'subtitle', label: '字幕语言' },
  { key: 'video_effect', label: '视频特效' },
  { key: 'platform', label: '发布平台' },
]

// 档案级条件展示（键同二级分类规则 criteria；值经映射缓存翻译为名称）
const ARCHIVE_FIELDS: { key: string; label: string; map?: 'genres' | 'companies' | 'keywords' | 'countries' | 'languages' }[] = [
  { key: 'title', label: '标题' },
  { key: 'genre_ids', label: '流派', map: 'genres' },
  { key: 'company_ids', label: '公司', map: 'companies' },
  { key: 'keyword_ids', label: '关键词', map: 'keywords' },
  { key: 'origin_country', label: '国家', map: 'countries' },
  { key: 'original_language', label: '语言', map: 'languages' },
  { key: 'year', label: '年份' },
]

function getConditionLines(item: any): { label: string; value: string; unset: boolean }[] {
  const c = item.conditions || {}
  const lines = CONDITION_FIELDS.map(({ key, label }) => {
    const val = c[key] || ''
    return { label, value: val || '无', unset: !val }
  })
  // 档案条件行：有条目才追加，值经映射缓存翻译为名称
  if (ARCHIVE_FIELDS.some(f => c[f.key])) {
    for (const f of ARCHIVE_FIELDS) {
      const raw = c[f.key] || ''
      lines.push({ label: f.label, value: (f.map ? translateIds(raw, f.map) : raw) || '无', unset: !raw })
    }
  }
  return lines
}

// 表单可填的匹配条件键，与 CONDITION_FIELDS / field_match.FIELD_MATCH_STRATEGY 一一对应
const FORM_CONDITION_KEYS = ['team', 'resolution', 'source', 'video_encode', 'audio_encode', 'subtitle', 'platform', 'video_effect']

function buildConditions(): Record<string, string> {
  const c: Record<string, string> = {}
  for (const k of FORM_CONDITION_KEYS) {
    const v = (blockForm as any)[k]?.trim()
    if (v) c[k] = v
  }
  return { ...c, ...archiveCriteria.value }
}

function resetForm() {
  blockForm.tmdb_id = ''
  blockForm.media_type = 'all'
  for (const k of FORM_CONDITION_KEYS) {
    ;(blockForm as any)[k] = ''
  }
  archiveCriteria.value = {}
}

function openAdd() {
  editingId.value = null
  resetForm()
  showFormModal.value = true
}

function openEdit(item: any) {
  editingId.value = item.id
  blockForm.tmdb_id = item.tmdb_id || ''
  blockForm.media_type = item.media_type || 'tv'
  const c = item.conditions || {}
  for (const k of FORM_CONDITION_KEYS) {
    ;(blockForm as any)[k] = c[k] || ''
  }
  archiveCriteria.value = Object.fromEntries(
    ARCHIVE_FIELDS.filter(f => c[f.key]).map(f => [f.key, c[f.key]])
  )
  showFormModal.value = true
}

function closeForm() {
  showFormModal.value = false
  editingId.value = null
  resetForm()
}

function errDetail(e: any, fallback: string) {
  return e?.response?.data?.detail || fallback
}

watch(() => props.show, (v) => { if (v) { fetchBlocklist(); fetchMappingCache() } else closeForm() })

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
    showError('留空 TMDB ID 时需至少填写一个匹配条件（如制作组）')
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
      <DialogTitle icon="mdi-shield-off-outline" icon-color="error" title="TMDB 屏蔽列表" @close="$emit('update:show', false)" />
      <v-divider />

      <v-card-text class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-4">
          命中屏蔽条目的资源，识别后直接标记已下载，跳过下载规则与追剧订阅。
          支持三种粒度：整部作品、指定作品内满足匹配条件的资源、以及不锚定作品的全局条件屏蔽（如屏蔽某制作组的全部发布）。
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
      <DialogTitle icon="mdi-shield-off-outline" icon-color="error" :title="editingId != null ? '编辑屏蔽条目' : '添加屏蔽条目'" @close="closeForm" />
      <v-divider />
      <v-card-text class="pa-4">
        <v-text-field v-model="blockForm.tmdb_id" label="TMDB ID（可留空）" placeholder="留空 = 按条件全局屏蔽" variant="outlined" density="compact" class="mb-3" />
        <v-select v-model="blockForm.media_type" label="类型" :items="typeOptions" variant="outlined" density="compact" class="mb-3" />

        <!-- 匹配条件：弹框较窄，一行一个 -->
        <div class="text-subtitle-2 font-weight-medium mb-2 mt-3">匹配条件</div>
        <v-row density="compact">
          <v-col v-for="f in CONDITION_FIELDS" :key="f.key" cols="12">
            <FieldConditionSelect v-model="(blockForm as any)[f.key]" :field="f.key" :label="f.label" />
          </v-col>
        </v-row>

        <!-- 档案条件：按作品 TMDB 档案匹配（同二级分类规则的条件维度） -->
        <div class="text-subtitle-2 font-weight-medium mb-2 mt-4">档案条件（按作品 TMDB 档案匹配）</div>
        <ArchiveCriteriaFields v-model="archiveCriteria" />

        <div class="text-caption text-medium-emphasis mt-2">
          多个条件需同时满足；全部留空 = 屏蔽整部作品（订阅同步标记已下载）；
          留空 TMDB ID 时至少填写一个条件，即全局条件屏蔽（档案条件按作品元数据判断，如屏蔽全部真人秀类作品）。
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
