/**
 * useDataCenter — 数据中心公共工具 composable
 *
 * 提供：
 * - getImg: 图片路径转换（使用相对路径避免 401）
 * - formatDbSize: 数据库大小格式化
 * - formatTime: ISO 时间格式化
 * - downloadJson: JSON 文件下载
 * - mappingCache / fetchMappingCache / translateIds: 映射缓存与翻译
 */
import { ref } from 'vue'
import { userMappingApi } from '@/api'

// --- 图片路径转换 ---
// 图片鉴权：后端通过 Referer 包含 Host 判断。
// 生产环境（前后端同一 origin）浏览器自动满足；
// 开发环境（Vite 代理）图片路径不走 changeOrigin，Host/Referer 保持原始值也能通过。
export function getImg(path: string): string {
  if (!path) return ''
  if (path.includes('/api/system/img') || path.includes('/api/system/bgm_img')) return path
  if (path.includes('image.tmdb.org')) {
    const parts = path.split('/')
    return `/api/system/img?path=/${parts[parts.length - 1]}`
  }
  // Bangumi 完整 URL → 转换为本地代理（后端 _proxy_img 在服务端已做，前端兜底）
  if (path.startsWith('http') && (path.includes('bgm') || path.includes('bangumi'))) {
    return `/api/system/bgm_img?url=${encodeURIComponent(path.replace('http:', 'https:'))}`
  }
  // TMDB 相对路径 → img 代理
  if (!path.startsWith('http')) return `/api/system/img?path=${path.startsWith('/') ? '' : '/'}${path}`
  return path
}

// --- 格式化工具 ---
export function formatDbSize(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}

export function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return '—' }
}

export function downloadJson(data: any, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export function parseCount(desc: string | undefined): number | null {
  if (!desc) return null
  const match = desc.match(/当前\s*(\d+)\s*条/)
  return match ? parseInt(match[1], 10) : null
}

// --- 映射缓存 ---
const mappingCache = ref<Record<string, Record<string, string>>>({
  countries: {}, languages: {}, genres: {}, keywords: {}, companies: {}
})
let mappingLoaded = false

export function useMappingCache() {
  async function fetchMappingCache() {
    if (mappingLoaded) return
    try {
      const [countries, languages, genres, keywords, companies] = await Promise.all([
        userMappingApi.getCountries(),
        userMappingApi.getLanguages(),
        userMappingApi.getGenres(),
        userMappingApi.getKeywords({ page: 1, page_size: 1000 }),
        userMappingApi.getCompanies({ page: 1, page_size: 1000 }),
      ])
      mappingCache.value = {
        countries: Object.fromEntries((countries as any[]).map((c: any) => [String(c.code || c.id).toUpperCase(), c.name_zh || c.name_en || c.name])),
        languages: Object.fromEntries((languages as any[]).map((l: any) => [String(l.code || l.id).toLowerCase(), l.name_zh || l.name_en || l.name])),
        genres: Object.fromEntries((genres as any[]).map((g: any) => [String(g.id), g.name_zh || g.name_en || String(g.id)])),
        keywords: Object.fromEntries(((keywords as any)?.items || keywords || []).map((k: any) => [String(k.id), k.name_zh || k.name_en || String(k.id)])),
        companies: Object.fromEntries(((companies as any)?.items || companies || []).map((c: any) => [String(c.id), c.name || String(c.id)])),
      }
      mappingLoaded = true
    } catch (e) {
      console.error('获取映射缓存失败', e)
    }
  }

  function translateIds(ids: string, type: 'genres' | 'companies' | 'keywords' | 'languages' | 'countries'): string {
    if (!ids) return ''
    return ids.split(',').map((s: string) => s.trim()).map(id => mappingCache.value[type]?.[id] || mappingCache.value[type]?.[id.toUpperCase()] || mappingCache.value[type]?.[id.toLowerCase()] || id).join(', ')
  }

  return { mappingCache, fetchMappingCache, translateIds }
}
