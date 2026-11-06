/**
 * 全局配置的只读缓存视图
 *
 * 用途：某个「单次/单任务」开关需要拿全局设置当默认值时（如「强制 AI 识别」），
 * 不必每处各写一遍 fetch —— 这里进程内只请求一次 `/api/config`，之后复用。
 *
 * 注意：只读、不负责保存。改配置仍走设置页（`configApi.saveConfig`）。
 */
import { configApi } from '@/api'

let cached: Promise<Record<string, any>> | null = null

/** 读取全局配置（进程内缓存；失败返回空对象，调用方自行兜底，不抛异常） */
export function getGlobalConfigCached(): Promise<Record<string, any>> {
  if (!cached) {
    cached = configApi
      .getConfig()
      .then((cfg: any) => (cfg && typeof cfg === 'object' ? cfg : {}))
      .catch(() => ({}))
  }
  return cached
}

/** 取某个布尔型全局开关的当前值（取不到时用 fallback） */
export async function getGlobalFlag(key: string, fallback = false): Promise<boolean> {
  const cfg = await getGlobalConfigCached()
  const value = cfg?.[key]
  return typeof value === 'boolean' ? value : fallback
}

/** 清缓存（设置页保存后如需立即反映，可调用） */
export function invalidateGlobalConfigCache() {
  cached = null
}
