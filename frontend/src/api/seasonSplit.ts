/**
 * 番剧分季拆分 API
 *
 * 对应后端 routers/season_split.py（前缀 /api/season-split）
 */
import { api } from './client'

export interface GroupBoundary {
  s: number
  e: number
}

export interface SplitGroup {
  order: number
  name: string
  start: GroupBoundary
  end: GroupBoundary
}

export interface SplitEpisode {
  season_number: number
  episode_number: number
  air_date: string
  name: string
  episode_type: string
}

export interface SplitCandidate {
  groups: SplitGroup[]
  warnings: string[]
}

export interface CompileResult {
  mapping: Record<string, Record<string, { season: number; episode: number }>>
  mapping_raw: Record<string, number[]>
  render_words: string
  /** 「连番号折算」追加的规则行（开关开启且 TMDB 有多季时才有） */
  absolute_rules?: string[]
  group_json: {
    id?: string
    description?: string
    groups: Array<{
      name: string
      air_date: string
      order: number
      episodes: Array<{ episode_number: number; season_number: number; order: number }>
    }>
  }
  rows: Array<{
    season: number
    episode: number
    org_season: number
    org_episode: number
    air_date: string
    name: string
    episode_type: string
  }>
  season_years?: Record<string, number>
  warnings: string[]
  replay_bad: Array<{ from: number[]; expect: number[]; got: number[] }>
  episode_total: number
}

export interface SplitRule {
  tmdb_id: number
  title: string
  status: 'draft' | 'active' | 'disabled'
  reference: string
  /** 创建来源：manual（工作台手动）/ sytmdb（一键导入）/ auto（识别时自动生成）/ ''（升级前的老数据，未知） */
  origin?: string | null
  groups: SplitGroup[]
  overrides: Record<string, unknown>
  excluded: Array<{ s: number; e: number } | [number, number]>
  names: Record<string, string>
  mapping: Record<string, Record<string, { season: number; episode: number }>>
  group_json: CompileResult['group_json']
  render_words: string
  tmdb_hash: string
  episode_total: number
  created_at?: string
  updated_at?: string
}

export interface ReferenceSummary {
  name: string
  split: boolean
  seasons: Array<{ season_number: number; episode_count: number; name: string }>
}

export interface PreviewResult {
  tmdb_id: number
  title: string
  reference: string
  references: Record<string, ReferenceSummary>
  need_split: boolean
  volatile: boolean
  status: string
  tmdb_hash: string
  stale: boolean
  tmdb: {
    number_of_seasons: number
    seasons: Array<{ season_number: number; episode_count: number; air_date?: string; name?: string }>
    poster_path: string
    first_air_date: string
  }
  episodes: SplitEpisode[]
  gaps: Array<{ after: GroupBoundary; days: number }>
  definition: Array<{
    season_number: number
    name: string
    episode_count: number
    include: Array<{ order: number; count: number; season_number?: number; episode_number?: number }>
  }>
  candidates: Record<string, SplitCandidate>
  default_basis: string
  suggested: CompileResult
  existing_rule: SplitRule | null
  gap_days: number
  gap_mark_days: number
  logs: string[]
}

export interface SeasonSplitSettings {
  mode: 'off' | 'preview' | 'on'
  scope: { organize?: boolean; subscription?: boolean; recognition_test?: boolean }
  blacklist: number[]
  exclude_patterns: string[]
  priority: string
  source: string
  use_source: boolean
  force_reference: boolean
  auto_generate: boolean
  auto_push_sytmdb: boolean
  gap_days: number
  ref_genre_ids: number[]
  ref_countries: string[]
  ref_season_min: number
  ref_season_max: number
  fixed_sizes: number[]
  gap_mark_days: number
  use_includes_rules: boolean
  /** 无需分季时按 TMDB 季边界附带「连番号折算」渲染词（不写 SYTMDB） */
  use_absolute_rules: boolean
  tvdb_key_configured: boolean
  cache: { count: number; version: string; loaded_at: string | null; mode: string }
}

export interface SavePayload {
  tmdb_id: number
  groups: SplitGroup[]
  overrides?: Record<string, unknown>
  excluded?: Array<{ s: number; e: number }>
  names?: Record<string, string>
  reference?: string
  status?: 'draft' | 'active' | 'disabled'
  render_words?: string
  /** 创建来源：留空 = 保留库里原值（新建时按 manual），一般不用传 */
  origin?: string
}

/** SYTMDB 里一条「带剧集组」的番（导入对话框用） */
export interface SytmdbCandidate {
  tmdb_id: number
  title: string
  year: number | null
  source: string | null
  /** 剧集组数量 */
  group_count: number
  /** 剧集组覆盖的集数（含 S0 特别篇） */
  episode_total: number
  /** 会被改写的集数（原坐标 ≠ 目标坐标） */
  changed_episodes: number
  /** 其中放进某个季的 S0 特别篇数量（会照搬，不丢弃） */
  specials: number
  /** 源里的重复集数量（保留第一次出现） */
  duplicates: number
  /** 会不会改动季号；false = 与 TMDB 原生结构一致，导入没有意义 */
  will_change: boolean
  existing: boolean
  existing_status: string
  existing_reference: string
  /** 已有规则的创建来源：manual / sytmdb / auto / ''（未知） */
  existing_origin: string
}

export interface SytmdbCandidatesResult {
  source: string
  scanned: number
  matched: number
  importable: number
  existing: number
  specials: number
  errors: Array<{ tmdb_id: number; title: string; error: string }>
  items: SytmdbCandidate[]
}

export interface SytmdbImportResult {
  imported: number
  skipped: Array<{ tmdb_id: number; reason: string }>
  failed: Array<{ tmdb_id: number; error: string }>
  items: Array<{
    tmdb_id: number
    title: string
    group_count: number
    episode_total: number
    changed_episodes: number
    specials: number
    duplicates: number
    rule_count: number
    replay_ok: boolean
    status: string
    will_change: boolean
    needs_overrides: boolean
    warnings: string[]
  }>
  scanned: number
  fetch_errors: Array<{ tmdb_id: number; title: string; error: string }>
  cache: SeasonSplitSettings['cache']
}

export interface BlacklistItem {
  tmdb_id: number
  title: string
  year: string | null
  poster_path: string
  is_custom: boolean
  source: string | null
  has_meta: boolean
}

export const seasonSplitApi = {
  listRules: (params?: { status?: string; q?: string; origin?: string; kind?: string }) =>
    api.get<{ items: SplitRule[]; cache: SeasonSplitSettings['cache'] }>('/api/season-split/rules', { params }),

  getRule: (tmdbId: number) => api.get<SplitRule>(`/api/season-split/rules/${tmdbId}`),

  saveRule: (payload: SavePayload) => api.put<SplitRule>('/api/season-split/rules', payload),

  deleteRule: (tmdbId: number) => api.delete<{ ok: boolean }>(`/api/season-split/rules/${tmdbId}`),

  preview: (payload: {
    tmdb_id: number
    priority?: string
    use_source?: boolean
    source?: string
    force_reference?: boolean
    skip_references?: boolean
  }) => api.post<PreviewResult>('/api/season-split/preview', payload),

  compile: (payload: {
    tmdb_id: number
    groups: SplitGroup[]
    overrides?: Record<string, unknown>
    excluded?: Array<{ s: number; e: number }>
    names?: Record<string, string>
    reference?: string
  }) => api.post<CompileResult & { tmdb_id: number; title: string; logs: string[] }>('/api/season-split/compile', payload),

  pushEpisodeGroup: (tmdbId: number) =>
    api.post<{ groups: number; message: string }>(`/api/season-split/push-episodegroup/${tmdbId}`),

  reload: () => api.post<{ ok: boolean; count: number; cache: SeasonSplitSettings['cache'] }>('/api/season-split/reload'),

  /** 列出 SYTMDB 上所有带剧集组的番（导入前体检） */
  sytmdbCandidates: () => api.get<SytmdbCandidatesResult>('/api/season-split/sytmdb/candidates'),

  /** 把 SYTMDB 的剧集组一键导入成规则（tmdb_ids 留空 = 全部需要拆分的） */
  importSytmdb: (payload: { tmdb_ids?: number[]; status?: string; overwrite?: boolean }) =>
    api.post<SytmdbImportResult>('/api/season-split/sytmdb/import', payload),

  getSettings: () => api.get<SeasonSplitSettings>('/api/season-split/settings'),

  updateSettings: (payload: Record<string, unknown>) =>
    api.put<SeasonSplitSettings>('/api/season-split/settings', payload),

  blacklistMeta: () => api.get<{ items: BlacklistItem[] }>('/api/season-split/blacklist/meta'),

  debug: (params: { tmdb_id: number; season: number; episode: number; filename?: string }) =>
    api.get<{
      from: number[]
      to: number[]
      changed: boolean
      reference: string
      rule_status: string
      render_words: string
    }>('/api/season-split/debug', { params }),
}
