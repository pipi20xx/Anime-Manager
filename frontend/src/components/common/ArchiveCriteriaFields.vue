<script setup lang="ts">
/**
 * ArchiveCriteriaFields — 作品档案级匹配条件编辑
 *
 * 与二级分类规则（数据中心 RulesTab）同一套条件维度与交互：
 * 流派/公司/关键词（远程搜索多选，可输入 ID 回车添加）、国家/语言（预载选项多选）、
 * 标题关键词/年份（手输，年份支持 2020 或 2020-2024 区间）。
 * modelValue 为逗号分隔字符串字典，键同后端 ARCHIVE_CONDITION_KEYS / 分类规则 criteria。
 */
import { ref, computed, watch, onMounted } from 'vue'
import { userMappingApi } from '@/api'
import { useMappingCache } from '@/composables/useDataCenter'

const props = withDefaults(defineProps<{
  modelValue?: Record<string, any> | null
}>(), { modelValue: () => ({}) })

const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, any>): void }>()

const { mappingCache, fetchMappingCache } = useMappingCache()

const selectedGenreIds = ref<string[]>([])
const selectedCompanyIds = ref<string[]>([])
const selectedKeywordIds = ref<string[]>([])
const selectedCountryCodes = ref<string[]>([])
const selectedLanguageCodes = ref<string[]>([])
const criteriaTitle = ref('')
const criteriaYear = ref('')

// 预载国家/语言选项
const countryOptions = ref<any[]>([])
const languageOptions = ref<any[]>([])
// 远程搜索选项
const genreSearchOptions = ref<any[]>([])
const companySearchOptions = ref<any[]>([])
const keywordSearchOptions = ref<any[]>([])
const genreSearchLoading = ref(false)
const companySearchLoading = ref(false)
const keywordSearchLoading = ref(false)

function splitIds(v: any): string[] {
  if (!v) return []
  return String(v).split(',').map((s: string) => s.trim()).filter(Boolean)
}

// 把已选中但不在选项里的 ID 用映射缓存补进选项，保证 chips 显示名称而非裸 ID
function withSelectedItems(items: any[], selected: string[], map: 'genres' | 'companies' | 'keywords' | 'countries' | 'languages'): any[] {
  const present = new Set(items.map(i => String(i.value)))
  const extra = selected
    .filter(id => !present.has(id))
    .map(id => ({ title: mappingCache.value[map]?.[id] || id, value: id }))
  return [...items, ...extra]
}

const genreItems = computed(() => withSelectedItems(genreSearchOptions.value, selectedGenreIds.value, 'genres'))
const companyItems = computed(() => withSelectedItems(companySearchOptions.value, selectedCompanyIds.value, 'companies'))
const keywordItems = computed(() => withSelectedItems(keywordSearchOptions.value, selectedKeywordIds.value, 'keywords'))
const countryItems = computed(() => withSelectedItems(countryOptions.value, selectedCountryCodes.value, 'countries'))
const languageItems = computed(() => withSelectedItems(languageOptions.value, selectedLanguageCodes.value, 'languages'))

function fieldsToCriteria(): Record<string, any> {
  const c: Record<string, any> = {}
  if (selectedGenreIds.value.length) c.genre_ids = selectedGenreIds.value.join(',')
  if (selectedCompanyIds.value.length) c.company_ids = selectedCompanyIds.value.join(',')
  if (selectedKeywordIds.value.length) c.keyword_ids = selectedKeywordIds.value.join(',')
  if (selectedCountryCodes.value.length) c.origin_country = selectedCountryCodes.value.join(',')
  if (selectedLanguageCodes.value.length) c.original_language = selectedLanguageCodes.value.join(',')
  if (criteriaTitle.value.trim()) c.title = criteriaTitle.value.trim()
  if (criteriaYear.value.trim()) c.year = criteriaYear.value.trim()
  return c
}

// 外部 → 内部（内容有变化才回填，避免与 emit 形成回环）
watch(() => props.modelValue, (c) => {
  const criteria = c || {}
  const next = [
    splitIds(criteria.genre_ids).join(','),
    splitIds(criteria.company_ids).join(','),
    splitIds(criteria.keyword_ids).join(','),
    splitIds(criteria.origin_country).join(','),
    splitIds(criteria.original_language).join(','),
    String(criteria.title || ''),
    String(criteria.year || ''),
  ]
  const cur = [
    selectedGenreIds.value.join(','), selectedCompanyIds.value.join(','), selectedKeywordIds.value.join(','),
    selectedCountryCodes.value.join(','), selectedLanguageCodes.value.join(','),
    criteriaTitle.value, criteriaYear.value,
  ]
  if (next.join('|') === cur.join('|')) return
  selectedGenreIds.value = splitIds(criteria.genre_ids)
  selectedCompanyIds.value = splitIds(criteria.company_ids)
  selectedKeywordIds.value = splitIds(criteria.keyword_ids)
  selectedCountryCodes.value = splitIds(criteria.origin_country)
  selectedLanguageCodes.value = splitIds(criteria.original_language)
  criteriaTitle.value = String(criteria.title || '')
  criteriaYear.value = String(criteria.year || '')
}, { immediate: true, deep: true })

// 内部 → 外部
watch([selectedGenreIds, selectedCompanyIds, selectedKeywordIds, selectedCountryCodes, selectedLanguageCodes, criteriaTitle, criteriaYear],
  () => emit('update:modelValue', fieldsToCriteria()), { deep: true })

onMounted(async () => {
  fetchMappingCache()
  // 预取各字段默认选项：点开即可直接下拉，无需先输入搜索
  remoteSearch('genre', '')
  remoteSearch('company', '')
  remoteSearch('keyword', '')
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
  } catch { /* 选项加载失败时仍可手输 */ }
})

async function remoteSearch(type: 'genre' | 'company' | 'keyword', query: string) {
  const loadingRef = type === 'genre' ? genreSearchLoading : type === 'company' ? companySearchLoading : keywordSearchLoading
  const optionsRef = type === 'genre' ? genreSearchOptions : type === 'company' ? companySearchOptions : keywordSearchOptions
  loadingRef.value = true
  try {
    const data = await userMappingApi.search({ type, q: query || '' })
    optionsRef.value = (data as any[]).map((r: any) => ({
      title: `${r.name} (ID:${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
      value: String(r.id),
    }))
  } catch { optionsRef.value = [] }
  finally { loadingRef.value = false }
}
</script>

<template>
  <v-combobox
    v-model="selectedGenreIds"
    :items="genreItems"
    :return-object="false"
    no-filter
    label="流派"
    placeholder="搜索选择流派，或输入 ID 回车添加"
    variant="outlined"
    density="compact"
    multiple
    chips
    closable-chips
    clearable
    :loading="genreSearchLoading"
    @update:search="(q: string) => remoteSearch('genre', q)"
    @update:menu="(open: boolean) => { if (open && genreSearchOptions.length === 0) remoteSearch('genre', '') }"
    class="mb-3"
  />

  <v-combobox
    v-model="selectedCompanyIds"
    :items="companyItems"
    :return-object="false"
    no-filter
    label="制作公司"
    placeholder="搜索选择公司，或输入 ID 回车添加"
    variant="outlined"
    density="compact"
    multiple
    chips
    closable-chips
    clearable
    :loading="companySearchLoading"
    @update:search="(q: string) => remoteSearch('company', q)"
    @update:menu="(open: boolean) => { if (open && companySearchOptions.length === 0) remoteSearch('company', '') }"
    class="mb-3"
  />

  <v-combobox
    v-model="selectedKeywordIds"
    :items="keywordItems"
    :return-object="false"
    no-filter
    label="关键词"
    placeholder="搜索选择关键词，或输入 ID 回车添加"
    variant="outlined"
    density="compact"
    multiple
    chips
    closable-chips
    clearable
    :loading="keywordSearchLoading"
    @update:search="(q: string) => remoteSearch('keyword', q)"
    @update:menu="(open: boolean) => { if (open && keywordSearchOptions.length === 0) remoteSearch('keyword', '') }"
    class="mb-3"
  />

  <v-combobox
    v-model="selectedCountryCodes"
    :items="countryItems"
    :return-object="false"
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

  <v-combobox
    v-model="selectedLanguageCodes"
    :items="languageItems"
    :return-object="false"
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

  <v-text-field v-model="criteriaTitle" label="名称匹配" placeholder="匹配标题关键词" variant="outlined" density="compact" class="mb-3" />
  <v-text-field v-model="criteriaYear" label="年份/范围" placeholder="2024 或 2020-2025" variant="outlined" density="compact" class="mb-1" />
</template>
