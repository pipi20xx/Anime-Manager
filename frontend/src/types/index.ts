// 类型统一导出
export * from './shared'

// ==========================================
// 认证
// ==========================================
export interface LoginParams {
  username: string
  password: string
  otp_code?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  status?: string
}

export interface VersionCheckResponse {
  latest_version: string
  cached: boolean
  cache_age_seconds?: number
  error?: string
}

// ==========================================
// 识别
// ==========================================
export interface FinalResult {
  filename: string
  title: string
  category: string
  year?: string
  season?: number
  episode?: string
  resolution?: string
  video_encode?: string
  audio_encode?: string
  video_effect?: string
  source?: string
  team?: string
  subtitle?: string
  processed_name?: string
  poster_path?: string
  release_date?: string
  tmdb_id?: string | number
  platform?: string
}

export interface RecognizeData {
  success: boolean
  logs: string[]
  final_result: FinalResult
  raw_meta: {
    cn_name?: string
    en_name?: string
    begin_season?: number
    begin_episode?: string
    resource_team?: string
    resource_type?: string
    resource_pix?: string
    video_encode?: string
    audio_encode?: string
    tags?: string[]
  }
  tmdb_match?: any
}

// ==========================================
// TMDB
// ==========================================
export interface TmdbSearchResult {
  id: number
  title?: string
  name?: string
  original_title?: string
  original_name?: string
  media_type: 'movie' | 'tv'
  poster_path?: string
  backdrop_path?: string
  overview?: string
  vote_average?: number
  release_date?: string
  first_air_date?: string
  genre_ids?: number[]
  popularity?: number
}

export interface TmdbDetail {
  id: number
  title?: string
  name?: string
  original_title?: string
  original_name?: string
  media_type?: 'movie' | 'tv'
  overview?: string
  poster_path?: string
  backdrop_path?: string
  vote_average?: number
  genres?: { id: number; name: string }[]
  number_of_seasons?: number
  number_of_episodes?: number
  seasons?: TmdbSeason[]
  status?: string
  first_air_date?: string
  release_date?: string
  production_companies?: any[]
  networks?: any[]
  credits?: {
    cast?: TmdbCast[]
    crew?: TmdbCrew[]
  }
  external_ids?: any
  videos?: any
  recommendations?: { results: TmdbSearchResult[] }
}

export interface TmdbSeason {
  id: number
  name: string
  season_number: number
  episode_count: number
  air_date?: string
  overview?: string
  poster_path?: string
}

export interface TmdbCast {
  id: number
  name: string
  character?: string
  profile_path?: string
  order?: number
}

export interface TmdbCrew {
  id: number
  name: string
  job?: string
  department?: string
  profile_path?: string
}

export interface TmdbPerson {
  id: number
  name: string
  biography?: string
  birthday?: string
  profile_path?: string
  place_of_birth?: string
  known_for_department?: string
}

// ==========================================
// Bangumi
// ==========================================
export interface BangumiSubject {
  id: number
  name: string
  name_cn?: string
  image?: string
  air_date?: string
  air_weekday?: number
  eps?: number
  rating?: { score: number; total: number }
  summary?: string
  type?: number
}

export interface CalendarItem {
  weekday: { id: number; en: string; cn: string }
  items: BangumiSubject[]
}

// ==========================================
// 订阅 / RSS
// ==========================================
export interface Feed {
  id?: number
  name: string
  url: string
  client_id?: number
  enabled?: boolean
  type?: string
  parser?: string
  interval?: number
  last_fetch?: string
  [key: string]: any
}

export interface Rule {
  id?: number
  name: string
  feed_id?: number
  pattern?: string
  quality_pattern?: string
  enabled?: boolean
  priority?: number
  action?: string
  target_dir?: string
  category?: string
  [key: string]: any
}

export interface DownloadHistory {
  guid?: string
  title?: string
  feed_id?: number
  rule_id?: number
  pub_date?: string
  download_url?: string
  status?: string
  [key: string]: any
}

export interface Subscription {
  id?: number
  name: string
  tmdb_id?: string | number
  media_type?: string
  feed_id?: number
  rule_id?: number
  enabled?: boolean
  target_dir?: string
  quality?: string
  season_number?: number
  total_episodes?: number
  downloaded_episodes?: number[]
  [key: string]: any
}

export interface SubscribedEpisode {
  id?: number
  subscription_id?: number
  episode_number?: number
  season_number?: number
  file_path?: string
  downloaded_at?: string
  [key: string]: any
}

// ==========================================
// 整理
// ==========================================
export interface RenameRule {
  id: string
  name: string
  movie_pattern?: string
  tv_pattern?: string
  [key: string]: any
}

export interface OrganizeTask {
  id: string
  name: string
  rule_id?: string
  source_dir: string
  target_dir: string
  action_type: 'move' | 'copy' | 'symlink'
  overwrite_mode?: boolean
  anime_priority?: boolean
  incremental_enabled?: boolean
  incremental_mode?: 'realtime' | 'polling'
  scheduler_enabled?: boolean
  scheduler_interval?: number
  monitor_interval?: number
  process_interval?: number
  ignore_file_regex?: string[]
  ignore_dir_regex?: string[]
  trigger_strm?: boolean
  [key: string]: any
}

export interface BackgroundTask {
  task_id: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  progress?: number
  total?: number
  message?: string
  started_at?: string
  completed_at?: string
  [key: string]: any
}

// ==========================================
// 下载客户端
// ==========================================
export interface DownloadClient {
  id?: number
  name: string
  type: string
  host: string
  port?: number
  username?: string
  password?: string
  enabled?: boolean
  [key: string]: any
}

// ==========================================
// 外观配置
// ==========================================
export interface AppearanceConfig {
  global: AppearanceGlobal
  modal: AppearanceModal
  dialog?: AppearanceModal
  card: AppearanceCard
  tabs: AppearanceTabs
  input: AppearanceInput
  search: AppearanceInput
  list: AppearanceList
  button: AppearanceButton
  instances?: Record<string, AppearanceInstanceOverrides>
  pages?: Record<string, AppearancePageConfig>
  [key: string]: any
}

export interface AppearanceGlobal {
  enabled: boolean
  background_image: string
  background_blur: number
  background_overlay_opacity: number
  layout_opacity: number
}

export interface AppearanceModal {
  enabled: boolean
  background_image: string
  background_blur: number
  background_opacity: number
  background_overlay_opacity: number
  border_color: string
  border_width: number
  border_radius: number
}

export interface AppearanceCard {
  enabled: boolean
  background_image: string
  background_opacity: number
  background_overlay_opacity: number
  border_radius: number
  blur: number
}

export interface AppearanceTabs {
  enabled: boolean
  nav_blur: number
  nav_opacity: number
  tab_active_bg: string
  tab_active_text_color: string
  tab_height: number
  tab_gap: number
  tab_padding: number
  tab_border_radius: number
  tab_font_size: number
}

export interface AppearanceInput {
  enabled: boolean
  bg_opacity: number
  border_radius: number
  height: number
  blur: number
}

export interface AppearanceList {
  enabled: boolean
  bg_opacity: number
  border_radius: number
  blur: number
}

export interface AppearanceButton {
  enabled: boolean
  border_radius: number
  height_medium: number
  height_small: number
  height_tiny: number
  text_color: string
  text_bg_hover: string
  text_bg_pressed: string
  warning_color: string
  danger_color: string
}

export interface AppearanceInstanceOverrides {
  modal?: Partial<AppearanceModal>
  dialog?: Partial<AppearanceModal>
  card?: Partial<AppearanceCard> & {
    border_color?: string
    border_width?: number
    border_style?: string
  }
  tabs?: Partial<AppearanceTabs> & {
    border_color?: string
    border_width?: number
    border_style?: string
  }
  input?: Partial<AppearanceInput> & {
    border_color?: string
    border_width?: number
    border_style?: string
  }
  search?: Partial<AppearanceInput> & {
    border_color?: string
    border_width?: number
    border_style?: string
  }
  list?: Partial<AppearanceList> & {
    border_color?: string
    border_width?: number
    border_style?: string
  }
  button?: Partial<AppearanceButton>
  text?: {
    color?: string
    secondary_color?: string
    tertiary_color?: string
    tint_color?: string
    input_color?: string
    shadow?: string
    font_weight?: string
    font_size?: number
  }
}

export interface AppearancePageBackground {
  enabled: boolean
  background_image: string
  background_blur: number
  background_overlay_opacity: number
  layout_opacity: number
}

export interface AppearancePageConfig extends AppearancePageBackground {
  overrides?: AppearanceInstanceOverrides
}
