<script setup lang="ts">
/**
 * RulesTab — 二级分类规则
 *
 * 对标旧前端 SecondaryRuleViewDesktop + ClassifierEditModal:
 * - 规则卡片列表 + 启用/禁用开关
 * - 编辑弹窗：流派/公司/关键词多选下拉（远程搜索），国家/语言支持自定义输入
 * - 导入导出、拖拽排序
 * - 卡片内容展示截断
 */
import { ref, reactive, onMounted, onActivated } from 'vue'
import { dataCenterApi } from '@/api'
import { userMappingApi } from '@/api/userMapping'
import { useNotification, useConfirm, downloadJson, useMappingCache, useDragSort } from '@/composables'

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()
const { mappingCache, fetchMappingCache, translateIds } = useMappingCache()

const rules = ref<any[]>([])
const rulesLoading = ref(false)

// 拖拽排序
const { dragIndex, dragOverIndex, onDragStart, onDragOver, onDragEnd } = useDragSort(rules, {
  onSort: async () => {
    try { await dataCenterApi.saveRules(rules.value) } catch (e) { showError('排序保存失败') }
  },
})
const showRuleEditModal = ref(false)
const isNewRule = ref(false)
const editingRuleIndex = ref(-1)
const ruleForm = reactive({
  id: undefined as number | undefined,
  name: '',
  target: 'all',
  enabled: true,
  criteria: {} as Record<string, any>,
})

// ===== 多选字段（用数组而非逗号分隔字符串） =====
const selectedGenreIds = ref<string[]>([])
const selectedCompanyIds = ref<string[]>([])
const selectedKeywordIds = ref<string[]>([])
const selectedCountryCodes = ref<string[]>([])
const selectedLanguageCodes = ref<string[]>([])

// 其他文本字段
const criteriaTitle = ref('')
const criteriaYear = ref('')

// ===== 远程搜索选项 =====
const genreSearchLoading = ref(false)
const genreSearchOptions = ref<any[]>([])
const companySearchLoading = ref(false)
const companySearchOptions = ref<any[]>([])
const keywordSearchLoading = ref(false)
const keywordSearchOptions = ref<any[]>([])

// ===== 预加载的国家/语言选项 =====
const countryOptions = ref<any[]>([])
const languageOptions = ref<any[]>([])

async function loadCountryLanguageOptions() {
  try {
    const [countries, languages] = await Promise.all([
      userMappingApi.getCountries(),
      userMappingApi.getLanguages(),
    ])
    countryOptions.value = (countries as any[]).map((c: any) => ({
      title: `${c.name_zh || c.name_en || c.name} (${c.code || c.id})`,
      value: String(c.code || c.id),
    }))
    languageOptions.value = (languages as any[]).map((l: any) => ({
      title: `${l.name_zh || l.name_en || l.name} (${l.code || l.id})`,
      value: String(l.code || l.id).toLowerCase(),
    }))
  } catch (e) { /* ignore */ }
}

// ===== 远程搜索函数 =====
async function searchGenres(query: string) {
  genreSearchLoading.value = true
  try {
    const data = await userMappingApi.search({ type: 'genre', q: query || '' })
    genreSearchOptions.value = (data as any[]).map((r: any) => ({
      title: `${r.name} (ID:${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
      value: String(r.id),
    }))
  } catch { genreSearchOptions.value = [] }
  finally { genreSearchLoading.value = false }
}

async function searchCompanies(query: string) {
  companySearchLoading.value = true
  try {
    const data = await userMappingApi.search({ type: 'company', q: query || '' })
    companySearchOptions.value = (data as any[]).map((r: any) => ({
      title: `${r.name} (ID:${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
      value: String(r.id),
    }))
  } catch { companySearchOptions.value = [] }
  finally { companySearchLoading.value = false }
}

async function searchKeywords(query: string) {
  keywordSearchLoading.value = true
  try {
    const data = await userMappingApi.search({ type: 'keyword', q: query || '' })
    keywordSearchOptions.value = (data as any[]).map((r: any) => ({
      title: `${r.name} (ID:${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
      value: String(r.id),
    }))
  } catch { keywordSearchOptions.value = [] }
  finally { keywordSearchLoading.value = false }
}

// ===== criteria 字段 ↔ 多选数组 转换 =====
function criteriaToFields(criteria: Record<string, any>) {
  selectedGenreIds.value = splitIds(criteria.genre_ids)
  selectedCompanyIds.value = splitIds(criteria.company_ids)
  selectedKeywordIds.value = splitIds(criteria.keyword_ids)
  selectedCountryCodes.value = splitIds(criteria.origin_country || criteria.country_codes)
  selectedLanguageCodes.value = splitIds(criteria.original_language)
  criteriaTitle.value = criteria.title || ''
  criteriaYear.value = criteria.year || ''
}

function fieldsToCriteria(): Record<string, any> {
  const c: Record<string, any> = {}
  if (selectedGenreIds.value.length) c.genre_ids = selectedGenreIds.value.join(',')
  if (selectedCompanyIds.value.length) c.company_ids = selectedCompanyIds.value.join(',')
  if (selectedKeywordIds.value.length) c.keyword_ids = selectedKeywordIds.value.join(',')
  if (selectedCountryCodes.value.length) c.origin_country = selectedCountryCodes.value.join(',')
  if (selectedLanguageCodes.value.length) c.original_language = selectedLanguageCodes.value.join(',')
  if (criteriaTitle.value) c.title = criteriaTitle.value
  if (criteriaYear.value) c.year = criteriaYear.value
  return c
}

function splitIds(ids: string | undefined): string[] {
  if (!ids) return []
  return ids.split(',').map((s: string) => s.trim()).filter(Boolean)
}

// ===== CRUD =====
async function fetchRules() {
  rulesLoading.value = true
  try {
    const res = await dataCenterApi.getRules()
    rules.value = Array.isArray(res) ? res : (res?.rules || res?.data || [])
  } catch (e) { showError('加载规则失败') }
  finally { rulesLoading.value = false }
}

function resetRuleForm() {
  ruleForm.id = undefined; ruleForm.name = ''; ruleForm.target = 'all'; ruleForm.enabled = true; ruleForm.criteria = {}
  criteriaToFields({})
  // 清空搜索选项
  genreSearchOptions.value = []; companySearchOptions.value = []; keywordSearchOptions.value = []
}

function openAddRule() { resetRuleForm(); isNewRule.value = true; editingRuleIndex.value = -1; showRuleEditModal.value = true }

function openEditRule(index: number) {
  resetRuleForm(); isNewRule.value = false; editingRuleIndex.value = index
  const raw = rules.value[index]
  Object.assign(ruleForm, { id: raw.id, name: raw.name || '', target: raw.target || 'all', enabled: raw.enabled !== false, criteria: raw.criteria || {} })
  criteriaToFields(raw.criteria || {})
  // 预加载已有选项，确保已选中的值能显示标签
  if (selectedGenreIds.value.length) searchGenres('')
  if (selectedCompanyIds.value.length) searchCompanies('')
  if (selectedKeywordIds.value.length) searchKeywords('')
  showRuleEditModal.value = true
}

async function handleSaveRule() {
  if (!ruleForm.name) { warning('请输入规则名称'); return }
  ruleForm.criteria = fieldsToCriteria()
  const ruleData = { ...ruleForm }
  if (isNewRule.value) rules.value.push(ruleData)
  else rules.value[editingRuleIndex.value] = ruleData
  try {
    await dataCenterApi.saveRules(rules.value)
    success('规则已保存'); showRuleEditModal.value = false; fetchRules()
  } catch (e) { showError('保存规则失败') }
}

async function deleteRule(index: number) {
  const rule = rules.value[index]
  const ok = await confirm({ title: '确认删除', content: `确定要删除规则 "${rule.name}" 吗？`, confirmColor: 'error' })
  if (!ok) return
  if (rule.id) { try { await dataCenterApi.deleteRule(rule.id); success('已删除') } catch (e) { showError('删除失败') } }
  rules.value.splice(index, 1)
}

async function toggleRuleEnabled(index: number) {
  rules.value[index].enabled = !rules.value[index].enabled
  try { await dataCenterApi.saveRules(rules.value) } catch (e) { showError('同步失败') }
}

async function exportRules() {
  try {
    const res = await dataCenterApi.exportRules()
    downloadJson(res, 'secondary_rules.json'); success('规则已导出')
  } catch (e) { showError('导出失败') }
}

async function importRules() {
  const input = document.createElement('input')
  input.type = 'file'; input.accept = '.json'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const importData = JSON.parse(text)
      const arr = Array.isArray(importData) ? importData : (importData?.rules || [])
      await dataCenterApi.importRules(arr, 'append')
      success(`已导入 ${arr.length} 条规则`); fetchRules()
    } catch (e) { showError('导入失败') }
  }
  input.click()
}

// ===== 卡片展示 =====
const CRITERIA_FIELDS: { key: string; label: string; map?: 'genres' | 'companies' | 'keywords' | 'countries' | 'languages' }[] = [
  { key: 'title', label: '标题' },
  { key: 'genre_ids', label: '流派', map: 'genres' },
  { key: 'company_ids', label: '公司', map: 'companies' },
  { key: 'keyword_ids', label: '关键词', map: 'keywords' },
  { key: 'origin_country', label: '国家', map: 'countries' },
  { key: 'original_language', label: '语言', map: 'languages' },
  { key: 'year', label: '年份' },
]

function getCriteriaLines(rule: any): { label: string; value: string; unrestricted: boolean }[] {
  const c = rule.criteria || {}
  return CRITERIA_FIELDS.map(({ key, label, map }) => {
    const raw = key === 'origin_country' ? (c.origin_country || c.country_codes) : c[key]
    const val = map ? translateIds(raw, map) : (raw || '')
    return { label, value: val || '不限制', unrestricted: !val }
  })
}

const targetItems = [
  { title: '全部', value: 'all' },
  { title: '剧集', value: 'tv' },
  { title: '电影', value: 'movie' },
]

onMounted(async () => {
  await Promise.all([fetchRules(), fetchMappingCache(), loadCountryLanguageOptions()])
})
onActivated(() => { if (rules.value.length === 0) fetchRules() })

defineExpose({ fetchRules })
</script>

<template>
  <div class="d-flex justify-end mb-4 ga-2">
    <v-btn color="info" variant="tonal" prepend-icon="mdi-upload-outline" @click="importRules">导入规则</v-btn>
    <v-btn color="info" variant="tonal" prepend-icon="mdi-download-outline" @click="exportRules">导出规则</v-btn>
    <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openAddRule">添加规则</v-btn>
  </div>

  <v-skeleton-loader v-if="rulesLoading" type="card@3" />

  <v-row v-else-if="rules.length > 0">
    <v-col
      v-for="(rule, index) in rules"
      :key="rule.id || index"
      cols="12" sm="6" md="4"
      draggable="true"
      :class="{ 'drag-sorting': dragIndex === index, 'drag-over': dragOverIndex === index }"
      @dragstart="onDragStart(index, $event)"
      @dragover="onDragOver(index, $event)"
      @dragend="onDragEnd"
    >
      <v-card class="glass-card manage-card cursor-pointer" :class="{ 'hover-lift': dragIndex === -1 }" @click="dragIndex === -1 && openEditRule(index)">
        <!-- 标题行 -->
        <div class="manage-card__header">
          <div class="d-flex align-center ga-2 manage-card__title">
            <span class="info-badge">#{{ index + 1 }}</span>
            <span class="text-truncate">{{ rule.name }}</span>
          </div>
          <v-switch
            :model-value="rule.enabled !== false"
            @update:model-value="toggleRuleEnabled(index)"
            density="compact"
            hide-details
            color="primary"
            size="small"
            class="manage-card__badge"
            @click.stop
          />
        </div>

        <!-- 信息区：固定 7 个字段，空值显示「不限制」 -->
        <div class="manage-card__body">
          <div class="manage-card__info" v-for="line in getCriteriaLines(rule)" :key="line.label">
            <span class="manage-card__info-label">{{ line.label }}</span>
            <span class="manage-card__info-value" :class="{ 'text-medium-emphasis': line.unrestricted }" :title="line.value">{{ line.value }}</span>
          </div>

          <div class="manage-card__tags">
            <v-chip size="x-small" variant="tonal" color="info">
              {{ rule.target === 'movie' ? '电影' : rule.target === 'tv' ? '剧集' : '全部' }}
            </v-chip>
          </div>
        </div>

        <v-divider />
        <v-card-actions class="manage-card__actions">
          <v-spacer />
          <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteRule(index)">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-col>
  </v-row>

  <div v-else class="text-center pa-8">
    <v-icon size="64" color="primary" class="mb-4">mdi-tag-off-outline</v-icon>
    <div class="text-h6 font-weight-medium">暂无分类规则</div>
    <div class="text-body-2 text-medium-emphasis mt-2">添加规则来自动分类整理后的文件</div>
  </div>

  <!-- 规则编辑弹窗 -->
  <v-dialog v-model="showRuleEditModal" max-width="800" scrollable>
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start color="primary">mdi-tag-outline</v-icon>
{{ isNewRule ? '创建分类规则' : '编辑分类规则' }}
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showRuleEditModal = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <!-- 基础设置 -->
        <div class="text-subtitle-2 font-weight-bold text-primary mb-2">基础设置</div>
        <v-text-field v-model="ruleForm.name" label="分类名称 (对应二级文件夹名)" variant="outlined" density="compact" class="mb-3" />
        <v-select v-model="ruleForm.target" label="适用对象" :items="targetItems" variant="outlined" density="compact" class="mb-3" />
        <v-switch v-model="ruleForm.enabled" label="启用" color="primary" density="compact" hide-details class="mb-3" />

        <v-divider class="my-3" />
        <div class="text-subtitle-2 font-weight-bold text-primary mb-2">匹配条件 (AND 逻辑)</div>

        <!-- 流派 — 多选 + 远程搜索 -->
        <v-autocomplete
          v-model="selectedGenreIds"
          :items="genreSearchOptions"
          label="流派"
          placeholder="搜索选择流派..."
          variant="outlined"
          density="compact"
          multiple
          chips
          closable-chips
          clearable
          :loading="genreSearchLoading"
          @update:search="searchGenres"
          @update:menu="(open: boolean) => { if (open && genreSearchOptions.length === 0) searchGenres('') }"
          class="mb-3"
        />

        <!-- 制作公司 — 多选 + 远程搜索 -->
        <v-autocomplete
          v-model="selectedCompanyIds"
          :items="companySearchOptions"
          label="制作公司"
          placeholder="搜索选择公司..."
          variant="outlined"
          density="compact"
          multiple
          chips
          closable-chips
          clearable
          :loading="companySearchLoading"
          @update:search="searchCompanies"
          @update:menu="(open: boolean) => { if (open && companySearchOptions.length === 0) searchCompanies('') }"
          class="mb-3"
        />

        <!-- 关键词 — 多选 + 远程搜索 -->
        <v-autocomplete
          v-model="selectedKeywordIds"
          :items="keywordSearchOptions"
          label="关键词"
          placeholder="搜索选择关键词..."
          variant="outlined"
          density="compact"
          multiple
          chips
          closable-chips
          clearable
          :loading="keywordSearchLoading"
          @update:search="searchKeywords"
          @update:menu="(open: boolean) => { if (open && keywordSearchOptions.length === 0) searchKeywords('') }"
          class="mb-3"
        />

        <v-row dense>
          <!-- 原始国家 — 多选 + 自定义输入 -->
          <v-col cols="12" sm="6">
            <v-autocomplete
              v-model="selectedCountryCodes"
              :items="countryOptions"
              label="原始国家"
              placeholder="下拉选择或输入国家代码"
              variant="outlined"
              density="compact"
              multiple
              chips
              closable-chips
              clearable
              class="mb-3"
            />
          </v-col>
          <!-- 原始语言 — 多选 + 自定义输入 -->
          <v-col cols="12" sm="6">
            <v-autocomplete
              v-model="selectedLanguageCodes"
              :items="languageOptions"
              label="原始语言"
              placeholder="下拉选择或输入语言代码"
              variant="outlined"
              density="compact"
              multiple
              chips
              closable-chips
              clearable
              class="mb-3"
            />
          </v-col>
        </v-row>

        <v-row dense>
          <v-col cols="12" sm="6">
            <v-text-field v-model="criteriaTitle" label="名称匹配" variant="outlined" density="compact" class="mb-3" placeholder="匹配标题关键词" />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model="criteriaYear" label="年份/范围" variant="outlined" density="compact" class="mb-3" placeholder="2024 或 2020-2025" />
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showRuleEditModal = false">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSaveRule">保存规则</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<!-- scoped 样式已迁移至 global.css .manage-card / .info-badge -->
<style scoped>
/* 固定信息区高度 — 7 行固定，保证所有卡片高度一致 */
:deep(.manage-card__body) {
  min-height: 180px;
}
</style>
