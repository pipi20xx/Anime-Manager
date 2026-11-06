<script setup lang="ts">
/**
 * 番剧分季拆分
 *
 * 规则库 / 分组工作台 / 高级（黑名单 + 调试器）。
 * 执行方式：分组 → 编译成渲染词 → 由现有 RenderEngine 在识别最后一步执行，
 * 所以「预览正确」= 「整理结果正确」，不需要往整理流程里插代码。
 */
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  seasonSplitApi,
  type CompileResult,
  type PreviewResult,
  type SavePayload,
  type SeasonSplitSettings,
  type ReferenceSummary,
  type SplitEpisode,
  type SplitGroup,
  type SplitRule,
} from '@/api/seasonSplit'
import { useConfirm, useNotification, useClipboard } from '@/composables'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()
const { copy } = useClipboard()

const activeTab = ref('library')
const loading = ref(false)

const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '规则库', icon: 'mdi-format-list-bulleted', tab: 'library' },
    { title: '分组工作台', icon: 'mdi-vector-polyline-edit', tab: 'workbench' },
    { title: '高级', icon: 'mdi-tune-variant', tab: 'advanced' },
  ],
  modelValue: activeTab,
})

// ---------------------------------------------------------------- 设置
const settings = reactive<SeasonSplitSettings>({
  mode: 'off',
  scope: { organize: true, subscription: false, recognition_test: false },
  blacklist: [],
  exclude_patterns: [],
  priority: 'tvdb, bangumi',
  use_source: false,
  force_reference: false,
  source: '',
  gap_days: 45,
  ref_genre_ids: [16],
  ref_countries: ['JP'],
  ref_season_min: 1,
  ref_season_max: 2,
  fixed_sizes: [12, 13],
  gap_mark_days: 21,
  use_includes_rules: true,
  tvdb_key_configured: false,
  cache: { count: 0, version: '', loaded_at: null, mode: 'off' },
})

const modeLabel = computed(
  () => ({ off: '已关闭', preview: '只预览', on: '已启用' } as Record<string, string>)[settings.mode] || settings.mode,
)
const modeColor = computed(
  () => ({ off: 'grey', preview: 'warning', on: 'success' } as Record<string, string>)[settings.mode] || 'grey',
)

const priorityOptions = [
  { title: 'TVDB → Bangumi', value: 'tvdb, bangumi' },
  { title: 'Bangumi → TVDB', value: 'bangumi, tvdb' },
  { title: '仅 TVDB', value: '仅 tvdb' },
  { title: '仅 Bangumi', value: '仅 bangumi' },
]

async function loadSettings() {
  try {
    const data = await seasonSplitApi.getSettings()
    Object.assign(settings, data)
    settings.scope = { organize: true, subscription: false, recognition_test: false, ...(data.scope || {}) }
    settings.ref_genre_ids = Array.isArray(data.ref_genre_ids) ? data.ref_genre_ids : [16]
    settings.ref_countries = Array.isArray(data.ref_countries) ? data.ref_countries : ['JP']
    settings.fixed_sizes = Array.isArray(data.fixed_sizes) ? data.fixed_sizes : [12, 13]
    settings.ref_season_min = data.ref_season_min ?? 1
    settings.ref_season_max = data.ref_season_max ?? 2
    settings.gap_mark_days = data.gap_mark_days ?? 21
    settings.use_includes_rules = data.use_includes_rules ?? true
    refGenreIdsText.value = (settings.ref_genre_ids || []).join(', ')
    refCountriesText.value = (settings.ref_countries || []).join(', ')
    fixedSizesText.value = (settings.fixed_sizes || []).join(', ')
  } catch (e: any) {
    showError(`读取设置失败: ${e.message}`)
  }
}

async function saveSettings() {
  try {
    const data = await seasonSplitApi.updateSettings({
      season_split_mode: settings.mode,
      season_split_scope: settings.scope,
      season_split_blacklist: settings.blacklist,
      season_split_priority: settings.priority,
      season_split_use_source: settings.use_source,
      season_split_force_reference: settings.force_reference,
      season_split_source: settings.source,
      season_split_gap_days: settings.gap_days,
      season_split_ref_genre_ids: settings.ref_genre_ids,
      season_split_ref_countries: settings.ref_countries,
      season_split_ref_season_min: settings.ref_season_min,
      season_split_ref_season_max: settings.ref_season_max,
      season_split_fixed_sizes: settings.fixed_sizes,
      season_split_gap_mark_days: settings.gap_mark_days,
      season_split_use_includes_rules: settings.use_includes_rules,
    })
    settings.cache = data.cache
    success('设置已保存')
  } catch (e: any) {
    showError(`保存设置失败: ${e.message}`)
  }
}

const tvdbInput = ref('')

async function saveTvdbKey() {
  if (!tvdbInput.value.trim()) return
  try {
    await seasonSplitApi.updateSettings({ tvdb_api_key: tvdbInput.value.trim() })
    settings.tvdb_key_configured = true
    tvdbInput.value = ''
    success('TVDB Key 已保存（留空则使用官方共用 Key）')
  } catch (e: any) {
    showError(`保存失败: ${e.message}`)
  }
}

async function reloadCache() {
  try {
    const data = await seasonSplitApi.reload()
    settings.cache = data.cache
    success(`规则缓存已重载：${data.count} 条`)
  } catch (e: any) {
    showError(`重载失败: ${e.message}`)
  }
}

const blacklistInput = ref('')

function addBlacklist() {
  const id = Number(blacklistInput.value)
  if (!id) {
    warning('请输入 TMDB 数字 ID')
    return
  }
  if (!settings.blacklist.includes(id)) settings.blacklist.push(id)
  blacklistInput.value = ''
}

// 高级：参照门槛 / 兜底的列表型输入（逗号分隔，blur 时解析并保存）
const refGenreIdsText = ref('')
const refCountriesText = ref('')
const fixedSizesText = ref('')

function parseIntList(text: string): number[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isInteger(n) && n > 0)
}

function parseStrList(text: string): string[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
}

function parseListTextsToSettings() {
  settings.ref_genre_ids = parseIntList(refGenreIdsText.value)
  settings.ref_countries = parseStrList(refCountriesText.value)
  settings.fixed_sizes = parseIntList(fixedSizesText.value)
}

function saveAdvanced() {
  parseListTextsToSettings()
  saveSettings()
}

async function resetReferenceDefaults() {
  settings.ref_genre_ids = [16]
  settings.ref_countries = ['JP']
  settings.ref_season_min = 1
  settings.ref_season_max = 2
  settings.fixed_sizes = [12, 13]
  settings.gap_mark_days = 21
  refGenreIdsText.value = '16'
  refCountriesText.value = 'JP'
  fixedSizesText.value = '12, 13'
  try {
    const data = await seasonSplitApi.updateSettings({
      season_split_ref_genre_ids: [16],
      season_split_ref_countries: ['JP'],
      season_split_ref_season_min: 1,
      season_split_ref_season_max: 2,
      season_split_fixed_sizes: [12, 13],
      season_split_gap_mark_days: 21,
    })
    settings.cache = data.cache
    success('已恢复默认并保存')
  } catch (e: any) {
    showError(`恢复默认失败: ${e.message}`)
  }
}

// ---------------------------------------------------------------- 规则库
const rules = ref<SplitRule[]>([])
const ruleSearch = ref('')
const ruleStatus = ref('')

async function loadRules() {
  loading.value = true
  try {
    const data = await seasonSplitApi.listRules({
      status: ruleStatus.value || undefined,
      q: ruleSearch.value || undefined,
    })
    rules.value = data.items || []
    settings.cache = data.cache
  } catch (e: any) {
    showError(`读取规则失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

const statusMeta: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'grey' },
  active: { label: '生效', color: 'success' },
  disabled: { label: '停用', color: 'warning' },
}

function statusOf(rule: SplitRule) {
  return statusMeta[rule.status] || { label: rule.status, color: 'grey' }
}

async function toggleRule(rule: SplitRule) {
  const next = rule.status === 'active' ? 'disabled' : 'active'
  try {
    await seasonSplitApi.saveRule({
      tmdb_id: rule.tmdb_id,
      groups: rule.groups,
      overrides: rule.overrides,
      excluded: rule.excluded as any,
      names: rule.names,
      reference: rule.reference,
      status: next,
    })
    success(`已${next === 'active' ? '启用' : '停用'}：${rule.title}`)
    await loadRules()
    await reloadCache()
  } catch (e: any) {
    showError(`操作失败: ${e.message}`)
  }
}

async function removeRule(rule: SplitRule) {
  const ok = await confirm({
    title: '删除分季规则',
    content: `确定删除「${rule.title}」(TMDB ${rule.tmdb_id}) 的分季规则？删除后该番恢复按 TMDB 原始季号整理。`,
  })
  if (!ok) return
  try {
    await seasonSplitApi.deleteRule(rule.tmdb_id)
    success('已删除')
    await loadRules()
    await reloadCache()
  } catch (e: any) {
    showError(`删除失败: ${e.message}`)
  }
}

async function pushGroup(rule: SplitRule | null | undefined) {
  if (!rule) {
    warning('请先保存规则，再写入 SYTMDB')
    return
  }
  const groupCount = (rule.groups || []).length
  const ok = await confirm({
    title: '写入 SYTMDB 剧集组',
    content:
      `将把「${rule.title || rule.tmdb_id}」的 ${groupCount} 个剧集组写入 SYTMDB，` +
      `并覆盖该番现有的剧集组，Emby 的季显示会立即随之变化。确定继续？`,
    confirmText: '写入',
    confirmColor: 'warning',
  })
  if (!ok) return
  try {
    const res = await seasonSplitApi.pushEpisodeGroup(rule.tmdb_id)
    success(`SYTMDB 已写入 ${res.groups} 个剧集组`)
  } catch (e: any) {
    showError(`写入失败: ${e.message}`)
  }
}

// ---------------------------------------------------------------- 工作台
const tmdbId = ref('')
const preview = ref<PreviewResult | null>(null)
const compileResult = ref<CompileResult | null>(null)
const groups = ref<SplitGroup[]>([])
const names = ref<Record<string, string>>({})
const excluded = ref<Array<{ s: number; e: number }>>([])
const reference = ref('manual')
const outputTab = ref('map')
const excludeInput = ref('')
let compileTimer: ReturnType<typeof setTimeout> | null = null
let suppressAutoCompile = false

const flatIndex = computed(() => {
  const map = new Map<string, number>()
  ;(preview.value?.episodes || []).forEach((ep, idx) => {
    map.set(`${ep.season_number}-${ep.episode_number}`, idx)
  })
  return map
})

const gapSet = computed(() => {
  const set = new Set<string>()
  ;(preview.value?.gaps || []).forEach((g) => set.add(`${g.after.s}-${g.after.e}`))
  return set
})

const basisLabel: Record<string, string> = {
  tvdb: 'TVDB 集数',
  bangumi: 'Bangumi 集数',
  curetmdb: 'CureTMDb 规则表',
  gap: '播出间隔',
  year: '播出年份',
  finale: '季结局标记',
  whole: '整季（不拆）',
  manual: '手动',
}

function labelOf(key: string) {
  if (key.startsWith('fixed')) {
    const n = key.slice(5)
    return /^\d+$/.test(n) ? `每 ${n} 集` : key
  }
  return basisLabel[key] || key || '—'
}

/** 组内集数（用摊平顺序算，跨季也对） */
function countOf(group: SplitGroup) {
  const a = flatIndex.value.get(`${group.start.s}-${group.start.e}`)
  const b = flatIndex.value.get(`${group.end.s}-${group.end.e}`)
  if (a === undefined || b === undefined) return 0
  return Math.abs(b - a) + 1
}

function rangeLabel(group: SplitGroup) {
  const fmt = (b: { s: number; e: number }) => `S${b.s}E${String(b.e).padStart(2, '0')}`
  return `${fmt(group.start)} → ${fmt(group.end)}`
}

/** 候选依据：附带「点了会切成几集」的提示，避免一堆按钮不知道结果 */
const candidateList = computed(() =>
  Object.entries(preview.value?.candidates || {}).map(([key, value]) => {
    const gs = value.groups || []
    const sizes = gs.map((g) => countOf(g)).filter((n) => n > 0)
    return {
      key,
      count: gs.length,
      sizes,
      sizeText: sizes.length ? sizes.join(' + ') : '无集数',
      noSplit: gs.length <= 1,
      warn: (value.warnings || []).length > 0,
    }
  }),
)

const recommendedCandidates = computed(() =>
  candidateList.value.filter((c) => c.key !== 'whole' && !c.key.startsWith('fixed')),
)
const manualCandidates = computed(() =>
  candidateList.value.filter((c) => c.key === 'whole' || c.key.startsWith('fixed')),
)

const coveredEpisodes = computed(() => compileResult.value?.episode_total ?? 0)

async function runPreview() {
  const id = Number(tmdbId.value)
  if (!id) {
    warning('请先填写 TMDB ID')
    return
  }
  loading.value = true
  try {
    const data = await seasonSplitApi.preview({ tmdb_id: id })
    preview.value = data
    const basis = data.default_basis && data.candidates?.[data.default_basis] ? data.default_basis : 'whole'
    reference.value = basis
    groups.value = normalizeGroups(data.candidates?.[basis]?.groups || [])
    excluded.value = []
    names.value = {}
    manualRenderWords.value = false
    compileResult.value = data.suggested || null
    activeTab.value = 'workbench'
    if (!groups.value.length) {
      warning('没有可用的自动分组，请切换右侧依据或手动加季')
    } else {
      success(`已生成方案：${labelOf(basis)}`)
    }
  } catch (e: any) {
    showError(`生成失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function pickBasis(key: string) {
  const candidate = preview.value?.candidates?.[key]
  if (!candidate) return
  reference.value = key
  groups.value = normalizeGroups(candidate.groups || [])
  scheduleCompile()
}

async function recompile() {
  if (!preview.value) return
  try {
    const data = await seasonSplitApi.compile({
      tmdb_id: preview.value.tmdb_id,
      groups: groups.value,
      overrides: {},
      excluded: excluded.value,
      names: names.value,
      reference: reference.value,
    })
    compileResult.value = data
  } catch (e: any) {
    showError(`编译失败: ${e.message}`)
  }
}

function scheduleCompile() {
  if (suppressAutoCompile) return
  if (compileTimer) clearTimeout(compileTimer)
  compileTimer = setTimeout(recompile, 500)
}

/** 兜底：把任何来源的分组（后端候选 / 已存规则 / 旧结构）收敛成固定形状，
 *  避免 start/end 缺失时模板取值报错、整块输入框渲染不出来。 */
function normalizeGroups(list: any[]): SplitGroup[] {
  return (list || []).map((raw: any, i: number) => {
    const start = raw?.start ?? {}
    const end = raw?.end ?? {}
    return {
      order: Number(raw?.order ?? i + 1) || i + 1,
      name: String(raw?.name || `第 ${i + 1} 季`),
      start: {
        s: Number(start.s ?? start.season ?? start.season_number ?? 1) || 1,
        e: Number(start.e ?? start.episode ?? start.episode_number ?? 1) || 1,
      },
      end: {
        s: Number(end.s ?? end.season ?? end.season_number ?? 1) || 1,
        e: Number(end.e ?? end.episode ?? end.episode_number ?? 1) || 1,
      },
    }
  })
}

watch(groups, scheduleCompile, { deep: true })

function addGroup() {
  const episodes = preview.value?.episodes || []
  if (!episodes.length) return
  const last = groups.value[groups.value.length - 1]
  // 新组从「上一组结束的下一集」开始，避免与上一组重叠
  let startIdx = 0
  if (last) {
    const idx = flatIndex.value.get(`${last.end.s}-${last.end.e}`)
    startIdx = idx === undefined ? episodes.length : idx + 1
  }
  if (startIdx >= episodes.length) {
    warning('已经覆盖到最后一集了')
    return
  }
  const head = episodes[startIdx]
  const tail = episodes[episodes.length - 1]
  groups.value.push({
    order: groups.value.length + 1,
    name: `第 ${groups.value.length + 1} 季`,
    start: { s: head.season_number, e: head.episode_number },
    end: { s: tail.season_number, e: tail.episode_number },
  })
}

function removeGroup(index: number) {
  groups.value.splice(index, 1)
  groups.value.forEach((g, i) => {
    g.order = i + 1
  })
}

function addExclude() {
  const text = excludeInput.value.trim()
  if (!text) return
  const m = text.match(/^(\d+)\s*-\s*(\d+)$/)
  if (!m) {
    warning('格式应为 季-集，例如 1-12')
    return
  }
  excluded.value.push({ s: Number(m[1]), e: Number(m[2]) })
  excludeInput.value = ''
  scheduleCompile()
}

async function applySave(status: 'draft' | 'active') {
  if (!preview.value) return
  if (preview.value.volatile && status === 'active') {
    const ok = await confirm({
      title: '番剧仍在连载',
      content: '该番状态为「连载中」，后续新增集数会让当前分季方案过期。仍要启用吗？',
    })
    if (!ok) return
  }
  try {
    const payload: SavePayload = {
      tmdb_id: preview.value.tmdb_id,
      groups: groups.value,
      overrides: {},
      excluded: excluded.value,
      names: names.value,
      reference: reference.value,
      status,
    }
    if (manualRenderWords.value) {
      payload.render_words = renderWordsText.value
    }
    const saved = await seasonSplitApi.saveRule(payload)
    // 保存后把刚存下的规则回填，让「写 SYTMDB」立刻可用（否则要重新生成一次）
    preview.value.existing_rule = saved as unknown as SplitRule
    manualRenderWords.value = false
    compileResult.value = buildSavedCompileResult(saved as unknown as SplitRule, preview.value?.episodes || [])
    await reloadCache()
    await loadRules()
    success(status === 'active' ? '已保存并启用' : '已保存为草稿')
  } catch (e: any) {
    showError(`保存失败: ${e.message}`)
  }
}

/** 用「已保存规则」构造工作台展示的编译结果：渲染词 / 映射 / 剧集组都取库里的原文，
 *  逐集明细 rows 由已存 mapping + TMDB 剧集列表补齐（标题/日期只是展示用）。 */
function buildSavedCompileResult(rule: SplitRule, episodes: SplitEpisode[]): CompileResult {
  const epByKey = new Map<string, SplitEpisode>()
  for (const ep of episodes) {
    epByKey.set(`${ep.season_number}-${ep.episode_number}`, ep)
  }
  const mapping = rule.mapping || {}
  const rows: CompileResult['rows'] = []
  for (const [s, eps] of Object.entries(mapping)) {
    for (const [e, dst] of Object.entries(eps)) {
      const raw = epByKey.get(`${s}-${e}`)
      rows.push({
        season: Number(dst?.season ?? 0),
        episode: Number(dst?.episode ?? 0),
        org_season: Number(s),
        org_episode: Number(e),
        air_date: raw?.air_date || '',
        name: raw?.name || '',
        episode_type: raw?.episode_type || '',
      })
    }
  }
  rows.sort((a, b) => a.season - b.season || a.episode - b.episode)
  return {
    mapping,
    mapping_raw: {},
    render_words: rule.render_words || '',
    group_json: rule.group_json || { groups: [] },
    rows,
    season_years: {},
    warnings: [],
    replay_bad: [],
    episode_total: rule.episode_total || rows.length,
  }
}

async function editRule(rule: SplitRule) {
  tmdbId.value = String(rule.tmdb_id)
  activeTab.value = 'workbench'
  loading.value = true
  try {
    // 只拉 TMDB 结构（左侧剧集列表需要），不重新取参照源、不重编译渲染词
    const data = await seasonSplitApi.preview({ tmdb_id: rule.tmdb_id, skip_references: true })
    preview.value = data
    suppressAutoCompile = true
    groups.value = normalizeGroups(rule.groups || [])
    names.value = rule.names || {}
    excluded.value = (rule.excluded || []).map((item: any) =>
      Array.isArray(item) ? { s: Number(item[0]), e: Number(item[1]) } : { s: Number(item.s), e: Number(item.e) },
    )
    reference.value = rule.reference || 'manual'
    manualRenderWords.value = false
    compileResult.value = buildSavedCompileResult(rule, data.episodes || [])
    await nextTick()
    suppressAutoCompile = false
    success('已载入规则（当前渲染词为已保存内容）')
  } catch (e: any) {
    showError(`载入规则失败: ${e.message}`)
  } finally {
    suppressAutoCompile = false
    loading.value = false
  }
}

// ---------------------------------------------------------------- 高级 / 调试
const debugForm = reactive({ tmdb_id: '', season: 1, episode: 1, filename: '' })
const debugResult = ref<any>(null)

async function runDebug() {
  try {
    debugResult.value = await seasonSplitApi.debug({
      tmdb_id: Number(debugForm.tmdb_id || tmdbId.value),
      season: Number(debugForm.season),
      episode: Number(debugForm.episode),
      filename: debugForm.filename || undefined,
    })
  } catch (e: any) {
    debugResult.value = null
    showError(`调试失败: ${e.message}`)
  }
}

const mappingRows = computed(() => compileResult.value?.rows || [])
const groupJsonText = computed(() => JSON.stringify(compileResult.value?.group_json || {}, null, 2))

// 渲染词默认跟随编译结果；用户手动改过后锁定，直到「重新生成 / 重新载入」
const renderWordsText = ref('')
const manualRenderWords = ref(false)

watch(compileResult, () => {
  if (!manualRenderWords.value) {
    renderWordsText.value = compileResult.value?.render_words || ''
  }
}, { immediate: true })

function onRenderWordsInput(val: string) {
  renderWordsText.value = val
  manualRenderWords.value = true
}

async function regenerateRenderWords() {
  manualRenderWords.value = false
  await recompile()
}

/** 参照源季集数摘要，如 12 + 14 */
function refSummary(ref: ReferenceSummary) {
  return (ref.seasons || []).map((s) => s.episode_count).join(' + ')
}

/** 两位补零（模板里用） */
function pad2(value: number | string) {
  return String(value ?? '').padStart(2, '0')
}

/** 逐集映射按「虚拟季」分组，渲染成卡片 */
const mappingBySeason = computed(() => {
  const buckets = new Map<number, typeof mappingRows.value>()
  for (const row of mappingRows.value) {
    const season = Number(row.season)
    if (!buckets.has(season)) buckets.set(season, [])
    buckets.get(season)!.push(row)
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([season, rows]) => ({ season, rows }))
})

/** TMDB 原始季按季分组，渲染成卡片（与分组定义同款） */
const rawSeasons = computed(() => {
  const buckets = new Map<number, SplitEpisode[]>()
  for (const ep of preview.value?.episodes || []) {
    const season = Number(ep.season_number)
    if (!buckets.has(season)) buckets.set(season, [])
    buckets.get(season)!.push(ep)
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([number, episodes]) => ({
      number,
      episodes,
      range: episodes.length
        ? `E${pad2(episodes[0].episode_number)} → E${pad2(episodes[episodes.length - 1].episode_number)}`
        : '',
    }))
})

onMounted(async () => {
  await Promise.all([loadSettings(), loadRules()])
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 顶部状态条 -->
    <v-card class="glass-card mb-4">
      <div class="d-flex flex-wrap align-center ga-3 pa-3">
        <v-btn-toggle
          v-model="settings.mode"
          mandatory
          divided
          density="compact"
          variant="outlined"
          @update:model-value="saveSettings"
        >
          <v-btn value="off" size="small" prepend-icon="mdi-power">关闭</v-btn>
          <v-btn value="preview" size="small" prepend-icon="mdi-eye-outline">只预览</v-btn>
          <v-btn value="on" size="small" prepend-icon="mdi-check-circle-outline">启用</v-btn>
        </v-btn-toggle>
        <v-chip :color="modeColor" size="small" variant="tonal" label>{{ modeLabel }}</v-chip>

        <v-divider vertical class="mx-1" />

        <v-switch
          v-model="settings.scope.organize"
          label="整理"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="saveSettings"
        />
        <v-switch
          v-model="settings.scope.subscription"
          label="订阅匹配"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="saveSettings"
        />
        <v-switch
          v-model="settings.scope.recognition_test"
          label="识别测试"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="saveSettings"
        />

        <v-spacer />
        <v-chip size="small" variant="tonal" prepend-icon="mdi-format-list-bulleted">
          生效规则 {{ settings.cache.count }}
        </v-chip>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" @click="reloadCache">重载缓存</v-btn>
      </div>
      <v-alert v-if="settings.mode === 'preview'" type="warning" variant="tonal" density="compact" class="mx-3 mb-3">
        只预览模式：规则不会注入识别流程，整理结果仍按 TMDB 原始季号。确认方案无误后切到「启用」。
      </v-alert>
    </v-card>

    <v-expansion-panels variant="accordion" flat class="mb-4">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2">
          <v-icon start size="small" color="primary">mdi-help-circle-outline</v-icon>
          这个功能怎么工作（拆分流程 · 生效方式 · 与渲染词的关系）
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="text-body-2 mb-2">
            把 TMDB 合并成一季的番（例如 S1 共 36 集）拆回「第 1 季 / 第 2 季…」，产出两样东西：
          </div>
          <ul class="text-body-2 pl-5 mb-3">
            <li><b>渲染词</b>：交给识别引擎在最后一步执行，改写整理用的季集号（→ <code>Season 2/S02E01</code>）</li>
            <li><b>剧集组 JSON</b>：点「写 SYTMDB」推送，让 Emby 按多季显示</li>
          </ul>

          <div class="section-title mb-1">拆分流程</div>
          <ol class="text-body-2 pl-5 mb-3">
            <li>规则表（高级里启用时）命中该 TMDB ID → 出一套候选</li>
            <li>TVDB、Bangumi <b>各出一套候选</b>（默认只对「日本动画且有效季数 1~2」，高级里可强制）</li>
            <li>三套候选并列在右侧「自动生成」里，可逐个切换对比；「参照优先级」只决定默认选中哪一个</li>
            <li>仅当某套参照的集数 &lt; TMDB 实际集数，才认为这套「需要拆分」（列表上方 chip 会标出来）</li>
            <li>拉全原始季 → 同日跨季去重 → 按播出日期摊平</li>
            <li>按选定定义逐季重灌：集号从 1 重排，切出虚拟季</li>
            <li>编译成渲染词 + 剧集组；没有参照时可用「播出间隔 / 年份 / finale / 固定集数」自动分组</li>
            <li>保存为「生效」后整理时自动套用；Emby 显示还要另外点「写 SYTMDB」</li>
          </ol>

          <div class="section-title mb-1">执行顺序</div>
          <div class="text-body-2 mb-3">
            你自己的「自定义渲染词」先执行 → 分季规则最后执行。两者冲突时以分季结果为准；
            要否决某番，用黑名单或直接在分组里改，不要靠再写一条规则盖回去。
          </div>

          <v-alert type="info" variant="tonal" density="compact">
            规则只在<b>识别最后一步</b>生效：识别结果里的季集号已经是拆分后的编号，
            因此 Emby 存在性检查、改名模板 <code>{'{season}'}/{'{episode}'}</code>、整理历史、STRM、通知都用同一套编号。
          </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <div>
      <!-- ============================================================ 规则库 -->
      <div v-if="activeTab === 'library'">
        <div class="d-flex ga-2 mb-4 flex-wrap align-center">
          <v-text-field
            v-model="ruleSearch"
            label="搜索番名或 TMDB ID"
            density="compact"
            variant="outlined"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            class="flex-grow-1"
            style="min-width: 220px"
            @keyup.enter="loadRules"
            @click:clear="ruleSearch = ''; loadRules()"
          />
          <v-select
            v-model="ruleStatus"
            :items="[
              { title: '全部状态', value: '' },
              { title: '草稿', value: 'draft' },
              { title: '生效', value: 'active' },
              { title: '停用', value: 'disabled' },
            ]"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 150px"
            @update:model-value="loadRules"
          />
          <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="loadRules">刷新</v-btn>
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="activeTab = 'workbench'">
            新建分季
          </v-btn>
        </div>

        <div class="text-caption text-medium-emphasis mb-3 px-1">
          共 {{ rules.length }} 条。只有状态为 <b>生效</b> 的规则会被注入识别；草稿/停用只是保存着不动。
          规则是唯一来源——不会自动从别处生成，也不会自动导入规则表。
        </div>

        <v-skeleton-loader v-if="loading && !rules.length" type="card@3" />

        <div v-else-if="rules.length" class="card-grid">
          <v-card v-for="rule in rules" :key="rule.tmdb_id" class="glass-card manage-card">
            <div class="manage-card__header">
              <div class="manage-card__title" :title="rule.title">{{ rule.title }}</div>
              <v-chip class="manage-card__badge" size="x-small" :color="statusOf(rule).color" variant="tonal" label>
                {{ statusOf(rule).label }}
              </v-chip>
            </div>

            <div class="manage-card__body">
              <div class="manage-card__info">
                <span class="manage-card__info-label">TMDB</span>
                <span class="manage-card__info-value font-mono">{{ rule.tmdb_id }}</span>
              </div>
              <div class="manage-card__info">
                <span class="manage-card__info-label">依据</span>
                <span class="manage-card__info-value">{{ labelOf(rule.reference) }}</span>
              </div>
              <div class="manage-card__info">
                <span class="manage-card__info-label">分组</span>
                <span class="manage-card__info-value">
                  {{ (rule.groups || []).length }} 组 · 覆盖 {{ rule.episode_total }} 集
                </span>
              </div>
              <div class="manage-card__info">
                <span class="manage-card__info-label">更新</span>
                <span class="manage-card__info-value">{{ rule.updated_at || '—' }}</span>
              </div>
            </div>

            <v-card-actions class="manage-card__actions">
              <v-spacer />
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-pencil" @click="editRule(rule)">
                编辑
              </v-btn>
              <v-btn size="small" variant="tonal" prepend-icon="mdi-power" @click="toggleRule(rule)">
                {{ rule.status === 'active' ? '停用' : '启用' }}
              </v-btn>
              <v-btn size="small" variant="tonal" prepend-icon="mdi-cloud-upload-outline" @click="pushGroup(rule)">
                剧集组
              </v-btn>
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="removeRule(rule)">
                删除
              </v-btn>
            </v-card-actions>
          </v-card>
        </div>

        <v-card v-else class="glass-card">
          <div class="empty-state pa-8 text-center">
            <v-icon size="40" color="primary" class="mb-2">mdi-format-list-bulleted</v-icon>
            <div class="text-body-2 text-medium-emphasis">还没有分季规则，去「分组工作台」新建一条</div>
          </div>
        </v-card>
      </div>

      <!-- ========================================================== 工作台 -->
      <div v-else-if="activeTab === 'workbench'">
        <div class="d-flex ga-2 mb-4 flex-wrap align-center">
          <v-text-field
            v-model="tmdbId"
            label="TMDB ID"
            density="compact"
            variant="outlined"
            prepend-inner-icon="mdi-movie-open-outline"
            hide-details
            style="max-width: 160px"
            @keyup.enter="runPreview"
          />
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-auto-fix" :loading="loading" @click="runPreview">
            生成方案
          </v-btn>
          <v-spacer />
          <template v-if="preview">
            <v-chip size="small" variant="tonal">{{ preview.title }}</v-chip>
            <v-chip v-if="preview.need_split" size="small" color="info" variant="tonal">需要拆分</v-chip>
            <v-chip v-else size="small" variant="tonal">结构一致</v-chip>
            <v-chip v-if="preview.volatile" size="small" color="warning" variant="tonal">连载中</v-chip>
            <v-chip v-if="preview.stale" size="small" color="error" variant="tonal">方案已过期</v-chip>
            <v-chip
              v-for="(ref, key) in preview.references"
              :key="key"
              size="small"
              variant="tonal"
              :color="ref.split ? 'info' : undefined"
              :title="ref.split ? '该参照源与 TMDB 结构不一致，需要拆分' : '该参照源与 TMDB 结构一致'"
            >
              {{ String(key).toUpperCase() }} {{ refSummary(ref) }}
            </v-chip>
          </template>
        </div>

        <div class="text-caption text-medium-emphasis mb-3 px-1">
          「生成方案」会同时拉取 TVDB 与 Bangumi（启用规则表时再加一份），右侧「自动生成」里逐个切换比较；
          <b>参照优先级 / 规则表 / 强制参照</b> 统一在「高级 → 默认参数」里设置。
          候选卡片右侧的数字是该依据会切成的集数（如 <code>12 + 14</code>）。
        </div>

        <v-card v-if="!preview" class="glass-card">
          <div class="empty-state pa-8 text-center">
            <v-icon size="40" color="primary" class="mb-2">mdi-call-split</v-icon>
            <div class="text-body-2 text-medium-emphasis">
              输入 TMDB ID 后点「生成方案」：会读取 TMDB 季结构，按参照源 / 播出间隔 / 年份 / 结局标记给出候选分组。
            </div>
          </div>
        </v-card>

        <v-row v-else>
          <!-- 原始季 -->
          <v-col cols="12" md="4">
            <div class="d-flex align-center flex-wrap ga-2 mb-2">
              <span class="section-title">TMDB 原始季</span>
              <v-chip size="x-small" variant="tonal">{{ preview.episodes.length }} 集</v-chip>
              <v-spacer />
              <span class="text-caption text-medium-emphasis">{{ rawSeasons.length }} 季</span>
            </div>

            <div class="season-stack">
              <v-card v-for="season in rawSeasons" :key="season.number" class="glass-card season-card">
                <div class="season-card__head">
                  <span class="season-card__title">第 {{ season.number }} 季</span>
                  <v-chip size="x-small" variant="tonal">{{ season.episodes.length }} 集</v-chip>
                  <v-spacer />
                  <span class="season-card__range font-mono">{{ season.range }}</span>
                </div>

                <div class="ep-list">
                  <template v-for="ep in season.episodes" :key="ep.episode_number">
                    <div class="ep-row text-caption">
                      <span class="font-mono">E{{ pad2(ep.episode_number) }}</span>
                      <span class="text-medium-emphasis">{{ ep.air_date || '—' }}</span>
                      <span class="ep-name text-truncate">{{ ep.name }}</span>
                      <v-icon v-if="ep.episode_type === 'finale'" size="x-small" color="warning">mdi-flag-checkered</v-icon>
                    </div>
                    <div v-if="gapSet.has(`${ep.season_number}-${ep.episode_number}`)" class="gap-line text-caption">
                      <v-icon size="x-small">mdi-arrow-down-thin</v-icon>
                      播出间隔 &gt; {{ preview.gap_mark_days }} 天
                    </div>
                  </template>
                </div>
              </v-card>
            </div>
          </v-col>

          <!-- 分组编辑器 -->
          <v-col cols="12" md="5">
            <div class="d-flex align-center flex-wrap ga-2 mb-2">
              <span class="section-title">分组定义</span>
              <v-chip size="x-small" variant="tonal">{{ labelOf(reference) }}</v-chip>
              <v-chip size="x-small" variant="tonal" color="primary">
                {{ groups.length }} 组 / {{ coveredEpisodes }} 集
              </v-chip>
              <v-spacer />
              <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addGroup">加一季</v-btn>
            </div>

            <div class="season-stack">
              <v-card v-for="(g, i) in groups" :key="i" class="glass-card season-card">
                <div class="season-card__head">
                  <span class="season-card__title">第 {{ g.order }} 季</span>
                  <v-chip size="x-small" variant="tonal">{{ countOf(g) || '—' }} 集</v-chip>
                  <v-spacer />
                  <span class="season-card__range font-mono">{{ rangeLabel(g) }}</span>
                  <v-btn
                    size="small"
                    variant="text"
                    color="error"
                    icon="mdi-delete-outline"
                    title="删除这一季"
                    @click="removeGroup(i)"
                  />
                </div>

                <v-text-field
                  v-model="g.name"
                  label="季名"
                  density="compact"
                  variant="outlined"
                  hide-details
                />

                <div class="season-row">
                  <span class="season-label">起始</span>
                  <span class="se-prefix">S</span>
                  <v-text-field
                    v-model.number="g.start.s"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="se-input"
                  />
                  <span class="se-prefix">E</span>
                  <v-text-field
                    v-model.number="g.start.e"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="se-input"
                  />
                </div>

                <div class="season-row">
                  <span class="season-label">结束</span>
                  <span class="se-prefix">S</span>
                  <v-text-field
                    v-model.number="g.end.s"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="se-input"
                  />
                  <span class="se-prefix">E</span>
                  <v-text-field
                    v-model.number="g.end.e"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="se-input"
                  />
                </div>
              </v-card>

              <v-card v-if="!groups.length" class="glass-card season-card season-card--empty">
                <div class="text-caption text-medium-emphasis">
                  还没有分组：点右上「加一季」，或从右侧「自动生成」里选一个依据
                </div>
              </v-card>

              <v-card class="glass-card season-card season-card--add" @click="addGroup">
                <v-icon size="28">mdi-plus</v-icon>
                <span class="text-caption">加一季</span>
              </v-card>
            </div>

            <div class="text-caption text-medium-emphasis mt-2 px-1">
              组内按「播出顺序」连续编号（第 1 组 = 第 1 季 E1 起）；下面的排除集不参与重排、保持原编号。
            </div>

            <div class="d-flex flex-wrap align-center ga-2 mt-3">
              <v-text-field
                v-model="excludeInput"
                label="排除集（季-集，回车添加）"
                density="compact"
                variant="outlined"
                hide-details
                style="max-width: 220px"
                @keyup.enter="addExclude"
              />
              <v-chip
                v-for="(ex, i) in excluded"
                :key="`${ex.s}-${ex.e}`"
                size="small"
                closable
                variant="tonal"
                @click:close="excluded.splice(i, 1); scheduleCompile()"
              >
                S{{ ex.s }}E{{ ex.e }}
              </v-chip>
              <span v-if="!excluded.length" class="text-caption text-medium-emphasis">
                排除的集保持原编号（总集篇 / 特别篇）
              </span>
            </div>

            <v-alert
              v-for="(w, i) in compileResult?.warnings || []"
              :key="i"
              type="warning"
              variant="tonal"
              density="compact"
              class="mt-2"
            >
              {{ w }}
            </v-alert>
          </v-col>

          <!-- 自动生成 -->
          <v-col cols="12" md="3">
            <div class="d-flex align-center flex-wrap ga-2 mb-2">
              <span class="section-title">自动生成</span>
              <v-spacer />
              <v-chip size="x-small" variant="tonal">{{ candidateList.length }} 种依据</v-chip>
            </div>

            <div class="season-stack">
              <v-card
                v-for="c in recommendedCandidates"
                :key="c.key"
                class="glass-card option-card"
                :class="{ 'option-card--active': reference === c.key }"
                @click="pickBasis(c.key)"
              >
                <v-icon size="18" class="option-card__icon">mdi-layers-triple-outline</v-icon>
                <span class="option-card__label">{{ labelOf(c.key) }}</span>
                <v-icon v-if="c.warn" size="14" color="warning" title="该依据会漏掉部分集数">mdi-alert-outline</v-icon>
                <v-spacer />
                <span class="option-card__value">{{ c.noSplit ? '不拆' : c.sizeText }}</span>
              </v-card>

              <div class="section-title text-medium-emphasis mt-1">按固定集数</div>

              <v-card
                v-for="c in manualCandidates"
                :key="c.key"
                class="glass-card option-card"
                :class="{ 'option-card--active': reference === c.key }"
                @click="pickBasis(c.key)"
              >
                <v-icon size="18" class="option-card__icon">mdi-grid</v-icon>
                <span class="option-card__label">{{ labelOf(c.key) }}</span>
                <v-icon v-if="c.warn" size="14" color="warning" title="该依据会漏掉部分集数">mdi-alert-outline</v-icon>
                <v-spacer />
                <span class="option-card__value">{{ c.noSplit ? '不拆' : c.sizeText }}</span>
              </v-card>

              <v-alert type="info" variant="tonal" density="compact" class="mt-1">
                右侧数字是「点下去会切成几集」（<code>12 + 14</code>）；<code>不拆</code> 表示整季一季。
                「播出间隔」按首播日期算，间隔 &gt; 阈值（默认 45 天，可在高级改）就切一刀；
                「季结局标记」依赖 TMDB 的 finale 标记；「固定集数」是最后的手工兜底。
              </v-alert>
            </div>
          </v-col>
        </v-row>

        <!-- 输出 -->
        <v-card v-if="preview" class="glass-card mt-4">
          <div class="d-flex align-center flex-wrap ga-2 pa-3">
            <v-tabs v-model="outputTab" density="compact" color="primary">
              <v-tab value="map">逐集映射</v-tab>
              <v-tab value="words">渲染词</v-tab>
              <v-tab value="json">剧集组 JSON</v-tab>
            </v-tabs>
            <v-spacer />
            <v-chip size="small" variant="tonal">覆盖 {{ compileResult?.episode_total || 0 }} 集</v-chip>
            <v-btn size="small" variant="tonal" prepend-icon="mdi-content-copy" @click="copy(renderWordsText, '渲染词已复制')">
              复制渲染词
            </v-btn>
            <v-btn size="small" variant="tonal" prepend-icon="mdi-file-code-outline" @click="copy(groupJsonText, '剧集组 JSON 已复制')">
              复制剧集组
            </v-btn>
            <v-btn size="small" color="success" variant="tonal" prepend-icon="mdi-check" @click="applySave('active')">
              保存并启用
            </v-btn>
            <v-btn
              size="small"
              color="primary"
              variant="tonal"
              prepend-icon="mdi-cloud-upload-outline"
              :disabled="!preview.existing_rule"
              @click="pushGroup(preview.existing_rule)"
            >
              写 SYTMDB
            </v-btn>
          </div>
          <v-divider />
          <div class="pa-2">
            <v-window v-model="outputTab">
              <v-window-item value="map">
                <div class="text-caption text-medium-emphasis px-2 pb-2">
                  虚拟季/集 = 改写后的编号（整理时用它命名、Emby 用它显示）；原始季/集 = TMDB 的编号。
                </div>
                <div v-if="mappingBySeason.length" class="card-grid">
                  <v-card v-for="grp in mappingBySeason" :key="grp.season" class="glass-card manage-card">
                    <div class="manage-card__header">
                      <div class="manage-card__title">第 {{ grp.season }} 季</div>
                      <v-chip class="manage-card__badge" size="x-small" variant="tonal">{{ grp.rows.length }} 集</v-chip>
                    </div>

                    <div class="manage-card__body map-body">
                      <div v-for="row in grp.rows" :key="row.episode" class="map-line">
                        <span class="map-line__virt">E{{ pad2(row.episode) }}</span>
                        <span class="map-line__org">← S{{ row.org_season }}E{{ pad2(row.org_episode) }}</span>
                        <span class="map-line__title" :title="row.name">{{ row.name || '—' }}</span>
                      </div>
                    </div>
                  </v-card>
                </div>

                <div v-else class="text-caption text-medium-emphasis pa-3">
                  当前分组是恒等映射（季集号不需要改），所以没有逐集改写记录。
                </div>
              </v-window-item>
              <v-window-item value="words">
                <div class="text-caption text-medium-emphasis px-2 pb-2">
                  由识别引擎在最后一步执行，比你自己的「自定义渲染词」晚一步；命中后季集号会直接写进识别结果。
                </div>
                <div v-if="manualRenderWords" class="d-flex align-center ga-2 px-2 pb-2">
                  <v-chip size="small" color="warning" variant="tonal">
                    已手动修改（保存时按此文本入库）
                  </v-chip>
                  <v-spacer />
                  <v-btn
                    size="small"
                    variant="text"
                    prepend-icon="mdi-refresh"
                    @click="regenerateRenderWords"
                  >
                    从分组重新生成
                  </v-btn>
                </div>
                <v-textarea
                  :model-value="renderWordsText"
                  @update:model-value="onRenderWordsInput"
                  class="render-words-editor"
                  variant="outlined"
                  density="compact"
                  rows="12"
                  hide-details
                  spellcheck="false"
                  placeholder="（分组为恒等映射，无需生成规则）"
                />
              </v-window-item>
              <v-window-item value="json">
                <div class="text-caption text-medium-emphasis px-2 pb-2">
                  点右上「写 SYTMDB」推送后，Emby 会按这些剧集组显示成多季；文件本身仍需按分季后编号命名。
                </div>
                <pre class="code-block">{{ groupJsonText }}</pre>
              </v-window-item>
            </v-window>
          </div>
        </v-card>
      </div>

      <!-- ============================================================ 高级 -->
      <div v-else-if="activeTab === 'advanced'">
        <div class="d-flex align-center ga-2 mb-4">
          <span class="section-title">高级设置</span>
          <v-spacer />
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-content-save" @click="saveAdvanced">
            保存设置
          </v-btn>
        </div>
        <v-row>
          <v-col cols="12" md="6">
            <v-card class="glass-card mb-4">
              <v-card-title class="text-subtitle-2">默认参数</v-card-title>
              <v-divider />
              <div class="pa-3 d-flex flex-column ga-3">
                <v-select
                  v-model="settings.priority"
                  :items="priorityOptions"
                  label="参照优先级（只决定默认选中哪个）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="d-flex flex-wrap ga-4">
                  <v-switch
                    v-model="settings.use_source"
                    label="启用 CureTMDb 规则表"
                    density="compact"
                    hide-details
                    color="primary"
                  />
                  <v-switch
                    v-model="settings.force_reference"
                    label="强制参照（跳过「日本动画 + 季数 1~2」门槛）"
                    density="compact"
                    hide-details
                    color="primary"
                  />
                  <v-switch
                    v-model="settings.use_includes_rules"
                    label="使用 includes 年份渲染词"
                    density="compact"
                    hide-details
                    color="primary"
                  />
                </div>
                <div class="text-caption text-medium-emphasis">
                  includes 渲染词按虚拟季首播年份做文件名包含匹配（例：<code>includes=2016</code>）；关闭后只生成集号/季号规则。
                </div>
                <v-text-field
                  v-model="settings.source"
                  label="CureTMDb 规则表地址（留空 = 不使用）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="text-caption text-medium-emphasis">
                  规则表命中会直接作为分季定义；留空时「生成方案」里勾了也不会去拉取。
                </div>
                <v-text-field
                  v-model.number="settings.gap_days"
                  type="number"
                  label="间隔切分阈值（天）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="text-caption text-medium-emphasis">
                  「播出间隔」作为切分依据时，相邻两集首播日期相差超过这个天数就切一刀。默认 45 天。
                </div>
                <div class="d-flex flex-wrap align-center ga-2">
                  <v-chip size="small" :color="settings.tvdb_key_configured ? 'success' : 'grey'" variant="tonal">
                    TVDB Key：{{ settings.tvdb_key_configured ? '已自定义' : '官方共用 Key' }}
                  </v-chip>
                  <v-text-field
                    v-model="tvdbInput"
                    label="覆盖为自己申请的 Key（可选）"
                    density="compact"
                    variant="outlined"
                    hide-details
                    type="password"
                    style="max-width: 320px"
                  />
                  <v-btn variant="tonal" @click="saveTvdbKey">保存</v-btn>
                </div>
              </div>
            </v-card>

            <v-card class="glass-card mb-4">
              <v-card-title class="text-subtitle-2 d-flex align-center">
                参照门槛与自动生成
                <v-spacer />
                <v-btn size="small" variant="text" prepend-icon="mdi-restore" @click="resetReferenceDefaults">
                  恢复默认
                </v-btn>
              </v-card-title>
              <v-divider />
              <div class="pa-3 d-flex flex-column ga-3">
                <div class="text-caption text-medium-emphasis">
                  自动拉取 TVDB / Bangumi 时的门槛（未开「强制参照」时生效）；列表留空表示不限制该项。
                </div>
                <v-text-field
                  v-model="refGenreIdsText"
                  label="动画类型（TMDB genre id，逗号分隔）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-text-field
                  v-model="refCountriesText"
                  label="出品国家（ISO 代码，逗号分隔）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="d-flex ga-2">
                  <v-text-field
                    v-model.number="settings.ref_season_min"
                    type="number"
                    label="有效季数下限"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                  <v-text-field
                    v-model.number="settings.ref_season_max"
                    type="number"
                    label="有效季数上限"
                    density="compact"
                    variant="outlined"
                    hide-details
                  />
                </div>
                <v-text-field
                  v-model="fixedSizesText"
                  label="固定集数兜底（每季集数，逗号分隔）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-text-field
                  v-model.number="settings.gap_mark_days"
                  type="number"
                  label="间隔虚线显示阈值（天）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <div class="text-caption text-medium-emphasis">
                  固定集数兜底会出现在右侧「自动生成」里；间隔虚线阈值只影响原始季列表的虚线显示，不影响切分。
                </div>
              </div>
            </v-card>

            <v-card class="glass-card">
              <v-card-title class="text-subtitle-2">番剧黑名单</v-card-title>
              <v-divider />
              <div class="pa-3 d-flex flex-column ga-2">
                <div class="text-caption text-medium-emphasis">黑名单里的番永远不会套用分季规则（规则可保留）。</div>
                <div class="d-flex flex-wrap ga-2">
                  <v-chip
                    v-for="(id, i) in settings.blacklist"
                    :key="id"
                    size="small"
                    closable
                    variant="tonal"
                    @click:close="settings.blacklist.splice(i, 1)"
                  >
                    {{ id }}
                  </v-chip>
                  <span v-if="!settings.blacklist.length" class="text-caption">（空）</span>
                </div>
                <div class="d-flex ga-2">
                  <v-text-field
                    v-model="blacklistInput"
                    label="添加 TMDB ID"
                    density="compact"
                    variant="outlined"
                    hide-details
                    style="max-width: 200px"
                    @keyup.enter="addBlacklist"
                  />
                  <v-btn variant="tonal" @click="addBlacklist">添加</v-btn>
                </div>
              </div>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="text-subtitle-2">映射调试器</v-card-title>
              <v-divider />
              <div class="pa-3 d-flex flex-column ga-3">
                <div class="text-caption text-medium-emphasis">
                  输入该番已保存规则里的一集原始坐标，回放规则看会被改成什么；填文件名可验证「年份 includes」规则是否命中。
                </div>
                <div class="d-flex flex-wrap ga-2">
                  <v-text-field v-model="debugForm.tmdb_id" label="TMDB ID" density="compact" variant="outlined" hide-details style="max-width: 140px" />
                  <v-text-field v-model.number="debugForm.season" type="number" label="季" density="compact" variant="outlined" hide-details style="max-width: 100px" />
                  <v-text-field v-model.number="debugForm.episode" type="number" label="集" density="compact" variant="outlined" hide-details style="max-width: 100px" />
                  <v-btn variant="tonal" @click="runDebug">回放</v-btn>
                </div>
                <v-text-field
                  v-model="debugForm.filename"
                  label="文件名（可选，用于验证 includes 年份规则）"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <v-alert v-if="debugResult" :type="debugResult.changed ? 'success' : 'info'" variant="tonal" density="compact">
                  S{{ debugResult.from[0] }}E{{ debugResult.from[1] }}
                  →
                  S{{ debugResult.to[0] }}E{{ debugResult.to[1] }}
                  （状态 {{ debugResult.rule_status }}，依据 {{ labelOf(debugResult.reference) }}）
                </v-alert>
                <pre v-if="debugResult" class="code-block">{{ debugResult.render_words }}</pre>
              </div>
            </v-card>
          </v-col>
        </v-row>
      </div>
    </div>
  </v-container>
</template>

<style scoped>

.ep-row {
  display: grid;
  grid-template-columns: 62px 86px 1fr 18px;
  gap: 6px;
  align-items: center;
  padding: 2px 4px;
  border-radius: 6px;
}

.ep-row:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

.render-words-editor :deep(textarea) {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.ep-name {
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.gap-line {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  color: rgb(var(--v-theme-warning));
  border-top: 1px dashed rgba(var(--v-theme-warning), 0.35);
  border-bottom: 1px dashed rgba(var(--v-theme-warning), 0.35);
}

.map-body {
  max-height: 320px;
  overflow-y: auto;
}

.map-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  line-height: 1.7;
  padding: 1px 0;
}

.map-line:hover {
  background: rgba(var(--v-theme-primary), 0.05);
}

.map-line__virt {
  flex: 0 0 34px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.map-line__org {
  flex: 0 0 76px;
  opacity: 0.5;
  font-variant-numeric: tabular-nums;
}

.map-line__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.75;
}

.season-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 2px;
}

.season-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  overflow: visible !important;
}

.season-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.season-card__title {
  font-size: 14px;
  font-weight: 700;
  white-space: nowrap;
}

.season-card__range {
  font-size: 11px;
  opacity: 0.5;
  white-space: nowrap;
}

.season-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.season-label {
  font-size: 11px;
  opacity: 0.55;
  white-space: nowrap;
  flex: 0 0 28px;
  width: 28px;
}

.se-prefix {
  font-size: 11px;
  opacity: 0.55;
  flex: 0 0 10px;
  width: 10px;
  text-align: center;
}

.se-input {
  flex: 0 0 84px;
  width: 84px;
  max-width: 84px;
}

.se-input :deep(input) {
  text-align: center;
}

.se-input :deep(input[type='number'])::-webkit-outer-spin-button,
.se-input :deep(input[type='number'])::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.se-input :deep(input[type='number']) {
  -moz-appearance: textfield;
  appearance: textfield;
}

.season-card--add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 84px;
  border-style: dashed !important;
  opacity: 0.75;
  cursor: pointer;
}

.season-card--add:hover {
  opacity: 1;
}

.season-card--empty {
  min-height: 60px;
}

.candidate-btn {
  text-transform: none;
}
.ep-list {
  max-height: 300px;
  overflow-y: auto;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
}

.option-card--active {
  border-color: rgb(var(--v-theme-primary)) !important;
}

.option-card__icon {
  opacity: 0.6;
}

.option-card__label {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.option-card__value {
  font-size: 11px;
  opacity: 0.6;
  white-space: nowrap;
}
</style>
