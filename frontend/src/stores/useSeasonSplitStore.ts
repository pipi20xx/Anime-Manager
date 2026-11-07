/**
 * 番剧分季 Store —— 规则库 / 分组工作台 / 高级（黑名单 + 调试器）共享状态
 *
 * 从旧版 SeasonSplitView.vue 单文件迁移而来，逻辑保持不变，只拆到 Pinia，
 * 供 Shell + 三个子 Tab 组件共用。
 */
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import {
  seasonSplitApi,
  type BlacklistItem,
  type CompileResult,
  type PreviewResult,
  type SavePayload,
  type SeasonSplitSettings,
  type ReferenceSummary,
  type SplitEpisode,
  type SplitGroup,
  type SplitRule,
  type SytmdbCandidate,
  type SytmdbImportResult,
} from '@/api/seasonSplit'
import { useConfirm, useNotification, useClipboard } from '@/composables'

export const useSeasonSplitStore = defineStore('seasonSplit', () => {
  const { success, error: showError, warning } = useNotification()
  const { confirm } = useConfirm()
  const { copy } = useClipboard()

  const activeTab = ref('library')
  const loading = ref(false)

  // ---------------------------------------------------------------- 设置
  const settings = reactive<SeasonSplitSettings>({
    mode: 'off',
    scope: { organize: true, subscription: false, recognition_test: false },
    blacklist: [],
    exclude_patterns: [],
    priority: 'tvdb, bangumi',
    use_source: false,
    force_reference: false,
    auto_generate: false,
    auto_push_sytmdb: false,
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
      settings.auto_generate = data.auto_generate ?? false
      settings.auto_push_sytmdb = data.auto_push_sytmdb ?? false
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
        season_split_auto_generate: settings.auto_generate,
        season_split_auto_push_sytmdb: settings.auto_push_sytmdb,
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
  const blacklistItems = ref<BlacklistItem[]>([])
  const blacklistLoading = ref(false)

  async function loadBlacklistMeta() {
    blacklistLoading.value = true
    try {
      const data = await seasonSplitApi.blacklistMeta()
      blacklistItems.value = data.items
    } catch (e: any) {
      showError(`读取黑名单失败: ${e.message}`)
    } finally {
      blacklistLoading.value = false
    }
  }

  async function addBlacklist() {
    const id = Number(blacklistInput.value)
    if (!id) {
      warning('请输入 TMDB 数字 ID')
      return
    }
    if (!settings.blacklist.includes(id)) settings.blacklist.push(id)
    blacklistInput.value = ''
    await saveSettings()
    await loadBlacklistMeta()
  }

  async function removeBlacklist(id: number) {
    const ok = await confirm({
      title: '移除黑名单',
      content: `把 TMDB ${id} 移出黑名单？移出后下次识别会重新评估。`,
    })
    if (!ok) return
    const idx = settings.blacklist.indexOf(id)
    if (idx >= 0) settings.blacklist.splice(idx, 1)
    await saveSettings()
    await loadBlacklistMeta()
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
  /** 来源过滤：'' 全部 / manual 手动 / sytmdb 导入 / auto 自动生成 / legacy 历史未知 */
  const ruleOrigin = ref('')

  async function loadRules() {
    loading.value = true
    try {
      const data = await seasonSplitApi.listRules({
        status: ruleStatus.value || undefined,
        q: ruleSearch.value || undefined,
        origin: ruleOrigin.value || undefined,
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

  /** 规则来源（创建方式）：手动 / SYTMDB 导入 / 识别时自动生成 / 升级前的老数据 */
  const originMeta: Record<string, { label: string; short: string; color: string; icon: string; hint: string }> = {
    manual: {
      label: '手动生成',
      short: '手动',
      color: 'primary',
      icon: 'mdi-account-edit-outline',
      hint: '在「分组工作台」里手动生成并保存的规则',
    },
    sytmdb: {
      label: 'SYTMDB 导入',
      short: 'SYTMDB',
      color: 'info',
      icon: 'mdi-cloud-download-outline',
      hint: '点「导入 SYTMDB」，直接把那边的剧集组搬过来的规则',
    },
    auto: {
      label: '自动生成',
      short: '自动',
      color: 'secondary',
      icon: 'mdi-robot-outline',
      hint: '识别时按「自动生成分季规则」开关自己生成的规则',
    },
  }

  const legacyOriginMeta = {
    label: '历史（未知来源）',
    short: '历史',
    color: 'grey',
    icon: 'mdi-help-circle-outline',
    hint: '升级前保存的规则，当时还没有记录来源，无法区分手动 / 自动',
  }

  function originMetaOf(key?: string | null) {
    const k = String(key || '').trim().toLowerCase()
    return originMeta[k] || legacyOriginMeta
  }

  function originOf(rule: SplitRule) {
    return originMetaOf(rule?.origin)
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

  // ---------------------------------------------------------------- SYTMDB 一键导入
  const sytmdbOpen = ref(false)
  const sytmdbLoading = ref(false)
  const sytmdbImporting = ref(false)
  const sytmdbSource = ref('')
  const sytmdbScanned = ref(0)
  const sytmdbItems = ref<SytmdbCandidate[]>([])
  const sytmdbSelected = ref<number[]>([])
  const sytmdbStatus = ref<'active' | 'draft'>('active')
  const sytmdbOverwrite = ref(false)
  const sytmdbResult = ref<SytmdbImportResult | null>(null)
  const sytmdbError = ref('')

  /** 可勾选的行：会改动季号，且（没有规则 或 允许覆盖） */
  const sytmdbSelectable = computed(() =>
    sytmdbItems.value.filter((row) => row.will_change && (sytmdbOverwrite.value || !row.existing)),
  )
  const sytmdbImportable = computed(() => sytmdbItems.value.filter((row) => row.will_change).length)
  const sytmdbExisting = computed(() => sytmdbItems.value.filter((row) => row.existing).length)

  function openSytmdbImport() {
    sytmdbOpen.value = true
    sytmdbResult.value = null
    sytmdbError.value = ''
    if (!sytmdbItems.value.length) loadSytmdbCandidates()
  }

  function closeSytmdbImport() {
    sytmdbOpen.value = false
  }

  async function loadSytmdbCandidates() {
    sytmdbLoading.value = true
    sytmdbError.value = ''
    sytmdbResult.value = null
    try {
      const data = await seasonSplitApi.sytmdbCandidates()
      sytmdbSource.value = data.source
      sytmdbScanned.value = data.scanned
      sytmdbItems.value = data.items || []
      // 默认全选「能导入且不会覆盖」的
      sytmdbSelected.value = sytmdbSelectable.value.map((row) => row.tmdb_id)
      if (!sytmdbItems.value.length) {
        warning('SYTMDB 上没有找到任何剧集组，先在那边把番分好季再回来导入')
      }
    } catch (e: any) {
      sytmdbItems.value = []
      sytmdbSelected.value = []
      sytmdbError.value = e?.message || String(e)
      showError(`读取 SYTMDB 剧集组失败: ${sytmdbError.value}`)
    } finally {
      sytmdbLoading.value = false
    }
  }

  function toggleSytmdbAll(checked: boolean) {
    sytmdbSelected.value = checked ? sytmdbSelectable.value.map((row) => row.tmdb_id) : []
  }

  function toggleSytmdbItem(tmdbId: number, checked: boolean) {
    const set = new Set(sytmdbSelected.value)
    if (checked) set.add(tmdbId)
    else set.delete(tmdbId)
    sytmdbSelected.value = [...set]
  }

  watch(sytmdbOverwrite, () => {
    // 关掉「覆盖已有规则」时，把已有规则的行从选择里剔除
    const allowed = new Set(sytmdbSelectable.value.map((row) => row.tmdb_id))
    sytmdbSelected.value = sytmdbSelected.value.filter((id) => allowed.has(id))
  })

  async function runSytmdbImport() {
    if (!sytmdbSelected.value.length) {
      warning('先勾选要导入的番')
      return
    }
    sytmdbImporting.value = true
    try {
      const data = await seasonSplitApi.importSytmdb({
        tmdb_ids: sytmdbSelected.value,
        status: sytmdbStatus.value,
        overwrite: sytmdbOverwrite.value,
      })
      sytmdbResult.value = data
      settings.cache = data.cache
      await loadRules()
      const parts = [`导入 ${data.imported} 条`]
      if (data.skipped.length) parts.push(`跳过 ${data.skipped.length} 条`)
      if (data.failed.length) parts.push(`失败 ${data.failed.length} 条`)
      if (data.failed.length) warning(parts.join('，'))
      else success(parts.join('，'))
      // 导入过的行标记成「已有规则」
      const imported = new Set(data.items.map((item) => item.tmdb_id))
      sytmdbItems.value = sytmdbItems.value.map((row) =>
        imported.has(row.tmdb_id) ? { ...row, existing: true, existing_status: sytmdbStatus.value } : row,
      )
      sytmdbSelected.value = sytmdbSelected.value.filter((id) => !imported.has(id))
    } catch (e: any) {
      showError(`导入失败: ${e.message}`)
    } finally {
      sytmdbImporting.value = false
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

  const mappingRows = computed(() => compileResult.value?.rows || [])
  const groupJsonText = computed(() => JSON.stringify(compileResult.value?.group_json || {}, null, 2))

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

  async function init() {
    await Promise.all([loadSettings(), loadRules()])
  }

  return {
    // 通用
    activeTab,
    loading,
    init,
    copy,

    // 设置
    settings,
    modeLabel,
    modeColor,
    priorityOptions,
    loadSettings,
    saveSettings,
    saveTvdbKey,
    reloadCache,
    tvdbInput,
    blacklistInput,
    blacklistItems,
    blacklistLoading,
    addBlacklist,
    removeBlacklist,
    loadBlacklistMeta,
    refGenreIdsText,
    refCountriesText,
    fixedSizesText,
    parseIntList,
    parseStrList,
    parseListTextsToSettings,
    saveAdvanced,
    resetReferenceDefaults,

    // 规则库
    rules,
    ruleSearch,
    ruleStatus,
    ruleOrigin,
    loadRules,
    statusOf,
    originOf,
    originMetaOf,
    toggleRule,
    removeRule,
    pushGroup,

    // SYTMDB 一键导入
    sytmdbOpen,
    sytmdbLoading,
    sytmdbImporting,
    sytmdbSource,
    sytmdbScanned,
    sytmdbItems,
    sytmdbSelected,
    sytmdbStatus,
    sytmdbOverwrite,
    sytmdbResult,
    sytmdbError,
    sytmdbSelectable,
    sytmdbImportable,
    sytmdbExisting,
    openSytmdbImport,
    closeSytmdbImport,
    loadSytmdbCandidates,
    toggleSytmdbAll,
    toggleSytmdbItem,
    runSytmdbImport,

    // 工作台
    tmdbId,
    preview,
    compileResult,
    groups,
    names,
    excluded,
    reference,
    outputTab,
    excludeInput,
    flatIndex,
    gapSet,
    labelOf,
    countOf,
    rangeLabel,
    candidateList,
    recommendedCandidates,
    manualCandidates,
    coveredEpisodes,
    runPreview,
    pickBasis,
    recompile,
    scheduleCompile,
    normalizeGroups,
    addGroup,
    removeGroup,
    addExclude,
    applySave,
    buildSavedCompileResult,
    editRule,
    renderWordsText,
    manualRenderWords,
    onRenderWordsInput,
    regenerateRenderWords,
    mappingRows,
    groupJsonText,
    refSummary,
    pad2,
    mappingBySeason,
    rawSeasons,

    // 高级 / 调试
    debugForm,
    debugResult,
    runDebug,
  }
})
