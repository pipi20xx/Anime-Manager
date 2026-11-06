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

export interface PreviewResult {
  tmdb_id: number
  title: string
  reference: string
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
  logs: string[]
}

export interface SeasonSplitSettings {
  mode: 'off' | 'preview' | 'on'
  scope: { organize?: boolean; subscription?: boolean; recognition_test?: boolean }
  blacklist: number[]
  exclude_patterns: string[]
  priority: string
  source: string
  gap_days: number
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
}

export const seasonSplitApi = {
  listRules: (params?: { status?: string; q?: string }) =>
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

  getSettings: () => api.get<SeasonSplitSettings>('/api/season-split/settings'),

  updateSettings: (payload: Record<string, unknown>) =>
    api.put<SeasonSplitSettings>('/api/season-split/settings', payload),

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
