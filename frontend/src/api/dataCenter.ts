/**
 * DataCenter API — 数据中心接口
 *
 * 对接后端 /api/tmdb_full 路由:
 * - 二级分类规则 CRUD
 * - 离线库元数据浏览/搜索
 * - 全量强制刷新
 * - 映射字典导出
 * - 离线字典搜索 (流派/公司/关键词)
 * - 服务状态
 */
import { api } from './client'

export const dataCenterApi = {
  // ===== 二级分类规则 =====
  /** 获取二级分类规则列表 */
  getRules: () =>
    api.get<any>('/api/tmdb_full/rules'),

  /** 保存/更新二级分类规则列表 */
  saveRules: (rules: any[]) =>
    api.post<any>('/api/tmdb_full/rules', rules),

  /** 导出二级分类规则 */
  exportRules: () =>
    api.get<any>('/api/tmdb_full/rules/export'),

  /** 导入二级分类规则 */
  importRules: (rules: any[], mode?: 'append' | 'replace') =>
    api.post<any>('/api/tmdb_full/rules/import', rules, { params: { mode: mode || 'append' } }),

  /** 删除单条规则 */
  deleteRule: (ruleId: number) =>
    api.delete<any>(`/api/tmdb_full/rules/${ruleId}`),

  // ===== 离线库元数据浏览 =====
  /** 分页浏览离线库元数据 */
  browseMeta: (params?: { page?: number; page_size?: number; search?: string }) =>
    api.get<any>('/api/tmdb_full/list', { params }),

  /** 导出映射字典 (流派/公司/关键词) */
  exportDictionary: () =>
    api.get<any>('/api/tmdb_full/export_dict'),

  // ===== 离线字典搜索 =====
  /** 在参考表(流派/公司/关键词)中搜索 */
  searchReference: (params: { q: string; type?: string }) =>
    api.get<any>('/api/tmdb_full/search_ref', { params }),

  // ===== 全量刷新 =====
  /** 触发全量强制刷新离线库 */
  refreshAll: (body?: { older_than_days?: number; year?: number; media_type?: string; tmdb_id?: string }) =>
    api.post<any>('/api/tmdb_full/refresh_all', body || {}),

  // ===== 元数据缓存管理 =====
  /** 手动添加/更新元数据缓存 */
  saveMetadata: (item: Record<string, any>) =>
    api.post<any>('/api/cache', item),

  /** 删除单条元数据缓存 */
  deleteMetadata: (mediaType: string, tmdbId: string) =>
    api.delete<any>(`/api/cache/${mediaType}/${tmdbId}`),

  /** 清空智能记忆 (指纹) */
  clearFingerprints: () =>
    api.post<any>('/api/cache/clear_fingerprints'),

  /** 智能清理无效记忆 */
  cleanupInvalidFingerprints: () =>
    api.post<any>('/api/cache/cleanup_invalid_fingerprints'),

  /** 清空下载黑名单 */
  clearBlacklist: () =>
    api.post<any>('/api/cache/clear_blacklist'),

  // ===== SYTMDB 同步 =====
  /** 从 SYTMDB 同步元数据 */
  syncSytmdb: (payload?: { address?: string; token?: string }) =>
    api.post<any>('/api/sytmdb/sync', payload || {}),

  // ===== 系统服务状态 =====
  /** 获取后台服务状态 */
  getServicesStatus: () =>
    api.get<any>('/api/system/services'),

  // ===== 数据库管理 =====
  /** 列出数据库表 (名称/行数/占用) */
  getDbTables: () =>
    api.get<any>('/api/system/db/tables'),

  /** 获取表结构 (主键列名) */
  getTableInfo: (tableName: string) =>
    api.get<any>(`/api/system/db/table_info/${tableName}`),

  /** 执行 SQL SELECT 查询 */
  queryDb: (sql: string) =>
    api.post<any>('/api/system/db/query', { sql }),

  /** 删除数据库行 */
  deleteDbRow: (payload: { table: string; pk_col: string; pk_val: any }) =>
    api.post<any>('/api/system/db/delete_row', payload),

  /** 更新数据库单元格 */
  updateDbCell: (payload: { table: string; pk_col: string; pk_val: any; col: string; val: any }) =>
    api.post<any>('/api/system/db/update_cell', payload),

  /** 清空数据库表 */
  truncateDbTable: (table: string) =>
    api.post<any>('/api/system/db/truncate', { table }),

  // ===== Emby 索引同步 =====
  /** 同步 Emby 库索引 */
  syncEmbyIndex: () =>
    api.post<any>('/api/tmdb/emby/sync-index'),

  // ===== 数据库引擎配置 =====
  /** 测试数据库连接 */
  testDbConnection: (config: any) =>
    api.post<any>('/api/system/db/test_connect', config),

  /** 保存数据库配置并应用 */
  saveDbConnection: (config: any) =>
    api.post<any>('/api/system/db/save_connect', config),
}
