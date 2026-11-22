/**
 * 前端资源版本错配的自愈兜底
 *
 * 场景：镜像/容器重建后 dist 里所有 chunk 都换了哈希，而当前页面内存中的入口
 * 仍指向旧哈希。此时懒加载路由会 404（后端已改为真 404，不再返回 200 + HTML），
 * 用户侧表现为白屏或某个页面打不开，且普通刷新可能仍命中旧入口。
 * 这里统一捕获这类「动态导入失败」，做一次性自动刷新，免去手动 Ctrl+F5。
 */
import type { Router } from 'vue-router'

const RELOAD_KEY = '__chunk_reload_at__'
// 刷新冷却：后端确实有问题时避免陷入无限刷新
const RELOAD_COOLDOWN_MS = 15_000

const CHUNK_ERROR_RE = new RegExp(
  [
    'dynamically imported module', // Chrome/Edge: Failed to fetch dynamically imported module
    'Importing a module script failed', // Firefox
    'Failed to load module script', // MIME 不符时 Chromium 的报错
    'error loading dynamically imported module', // Safari
    'Loading chunk \\d+ failed', // webpack 风格（历史构建残留）
    'ChunkLoadError',
    'MIME type of "?text/html', // 兜底 HTML 被当成 JS 的典型报错
  ].join('|'),
  'i',
)

function isChunkLoadError(value: unknown): boolean {
  if (!value) return false
  const text = value instanceof Error ? `${value.name} ${value.message}` : String(value)
  return CHUNK_ERROR_RE.test(text)
}

function isAssetScriptTarget(target: unknown): boolean {
  // <script type="module" src="/assets/xxx.js"> 加载失败只触发 error 事件、没有 message，
  // 只能按目标节点判断，否则会误吞图片等其它资源错误。
  if (typeof HTMLScriptElement === 'undefined' || !(target instanceof HTMLScriptElement)) return false
  const src = target.src || ''
  return /\/assets\/|\.m?js(\?|$)/.test(src)
}

function reloadOnce(reason: string): void {
  const now = Date.now()
  let last = 0
  try {
    last = Number(sessionStorage.getItem(RELOAD_KEY) || 0)
  } catch {
    /* 隐私模式下 sessionStorage 不可用，忽略 */
  }
  if (now - last < RELOAD_COOLDOWN_MS) {
    console.error(`[资源版本] 动态导入失败（${reason}），刚刷新过，跳过自动刷新；请手动 Ctrl+F5。`)
    return
  }
  try {
    sessionStorage.setItem(RELOAD_KEY, String(now))
  } catch {
    /* 同上 */
  }
  console.warn(`[资源版本] 检测到前端资源已更新（${reason}），正在刷新以加载新版本…`)
  window.location.reload()
}

export function installChunkReloadGuard(router: Router): void {
  // 1) 路由懒加载失败（最常见：点开某个页签时）
  router.onError((error) => {
    if (!isChunkLoadError(error)) return
    reloadOnce('router')
  })

  // 2) 页面内其它动态 import 的 promise 拒绝
  window.addEventListener('unhandledrejection', (event) => {
    if (!isChunkLoadError(event.reason)) return
    reloadOnce('unhandledrejection')
  })

  // 3) <script> 标签直接加载失败（模块 MIME 不符时走这里）
  window.addEventListener(
    'error',
    (event) => {
      if (!isAssetScriptTarget((event as ErrorEvent).target)) return
      reloadOnce('script')
    },
    true,
  )
}
