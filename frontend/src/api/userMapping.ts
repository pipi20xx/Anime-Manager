/**
 * UserMapping API — 用户自定义映射接口
 *
 * 对接后端 /api/user_mapping 路由:
 * - 流派 / 公司 / 关键词 / 语言 / 国家 CRUD
 * - 从 TMDB 参考表导入
 * - 导入导出备份
 * - 参考表统计
 * - 搜索映射
 */
import { api } from './client'

export interface MappingItem {
  id: number | string
  name_zh?: string
  name_en?: string
  name?: string
  country?: string
  code?: string
  source?: string
}

export const userMappingApi = {
  // ===== 流派 =====
  getGenres: (q?: string) =>
    api.get<MappingItem[]>('/api/user_mapping/genres', { params: { q } }),

  saveGenre: (item: MappingItem) =>
    api.post<any>('/api/user_mapping/genres', item),

  deleteGenre: (id: number) =>
    api.delete<any>(`/api/user_mapping/genres/${id}`),

  // ===== 公司 =====
  getCompanies: (params: { page?: number; page_size?: number; q?: string }) =>
    api.get<any>('/api/user_mapping/companies', { params }),

  saveCompany: (item: MappingItem) =>
    api.post<any>('/api/user_mapping/companies', item),

  deleteCompany: (id: number) =>
    api.delete<any>(`/api/user_mapping/companies/${id}`),

  // ===== 关键词 =====
  getKeywords: (params: { page?: number; page_size?: number; q?: string }) =>
    api.get<any>('/api/user_mapping/keywords', { params }),

  saveKeyword: (item: MappingItem) =>
    api.post<any>('/api/user_mapping/keywords', item),

  deleteKeyword: (id: number) =>
    api.delete<any>(`/api/user_mapping/keywords/${id}`),

  // ===== 语言 =====
  getLanguages: (q?: string) =>
    api.get<MappingItem[]>('/api/user_mapping/languages', { params: { q } }),

  saveLanguage: (item: { code: string; name_zh?: string; name_en?: string }) =>
    api.post<any>('/api/user_mapping/languages', item),

  deleteLanguage: (code: string) =>
    api.delete<any>(`/api/user_mapping/languages/${code}`),

  // ===== 国家 =====
  getCountries: (q?: string) =>
    api.get<MappingItem[]>('/api/user_mapping/countries', { params: { q } }),

  saveCountry: (item: { code: string; name_zh?: string; name_en?: string }) =>
    api.post<any>('/api/user_mapping/countries', item),

  deleteCountry: (code: string) =>
    api.delete<any>(`/api/user_mapping/countries/${code}`),

  // ===== 搜索 / 导入 / 导出 =====
  /** 搜索映射（优先用户自定义，回退到参考表） */
  search: (params: { type?: string; q?: string }) =>
    api.get<MappingItem[]>('/api/user_mapping/search', { params }),

  /** 从 TMDB 参考表导入 */
  importFromRef: (type?: string) =>
    api.post<any>(`/api/user_mapping/import_from_ref`, undefined, { params: { type } }),

  /** 获取参考表数据统计 */
  getRefCounts: () =>
    api.get<any>('/api/user_mapping/ref_counts'),

  /** 导出所有用户映射 */
  exportMappings: () =>
    api.get<any>('/api/user_mapping/export'),

  /** 导入用户映射 */
  importMappings: (data: any, mode?: 'append' | 'replace') =>
    api.post<any>('/api/user_mapping/import', data, { params: { mode: mode || 'append' } }),

  /** 恢复内置默认映射数据 (清空当前数据后重写硬编码默认值) */
  resetDefaults: (type?: string) =>
    api.post<any>('/api/user_mapping/reset_defaults', undefined, { params: { type: type || 'all' } }),
}
