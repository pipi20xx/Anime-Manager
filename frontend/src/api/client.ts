/**
 * API 客户端封装 — 基于 Fetch
 *
 * 设计参考: sytmdb/src/api/client.ts
 * - 自动注入 Authorization 头
 * - 401 自动登出
 * - 泛型返回
 * - FormData 支持
 */

interface ApiOptions extends RequestInit {
  baseUrl?: string
  params?: Record<string, string | number | boolean | undefined | null | (string | number | boolean)[]>
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/** 读取当前登录 token（localStorage 存的是 JWT / 外部 API Token） */
export function getAccessToken(): string {
  return localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token') || ''
}

/**
 * 认证头 — 供无法走 apiFetch 的场景复用：
 * 流式 NDJSON / SSE / 原生 fetch / EventSource 等。
 * 注意：手写 fetch 时漏掉它会被后端中间件直接判 401。
 */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getAccessToken()
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(extra || {}) }
}

/** 拼接 baseUrl + query string（apiFetch / apiStream 共用） */
function buildUrl(
  endpoint: string,
  baseUrl: string,
  params?: ApiOptions['params'],
): string {
  let url = `${baseUrl}${endpoint}`
  if (!params) return url

  const queryString = new URLSearchParams()
  for (const key in params) {
    const value = params[key]
    if (value !== undefined && value !== null) {
      if (Array.isArray(value)) {
        value.forEach((v) => queryString.append(key, String(v)))
      } else {
        queryString.append(key, String(value))
      }
    }
  }
  if (queryString.toString()) {
    url += (url.includes('?') ? '&' : '?') + queryString.toString()
  }
  return url
}

/**
 * 流式请求 — 返回原始 Response（不解析 body），用于 NDJSON / SSE 读取。
 * 自动注入 Authorization 头；401 时同样清理登录态并跳登录页。
 */
export async function apiStream(
  endpoint: string,
  options?: ApiOptions,
): Promise<Response> {
  const { baseUrl = API_BASE_URL, params, headers, body, method = 'GET', ...rest } = options || {}

  const config: RequestInit = {
    method,
    headers: authHeaders({
      ...(body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...(headers as Record<string, string> | undefined),
    }),
    body: body
      ? (body instanceof FormData || typeof body === 'string' ? body : JSON.stringify(body))
      : undefined,
    ...rest,
  }

  const response = await fetch(buildUrl(endpoint, baseUrl, params), config)

  if (response.status === 401) {
    localStorage.removeItem('apm_access_token')
    localStorage.removeItem('apm_username')
    localStorage.removeItem('apm_external_token')
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
  }

  return response
}

export async function apiFetch<T>(
  endpoint: string,
  options?: ApiOptions,
): Promise<T> {
  const { baseUrl = API_BASE_URL, params, headers, body, method = 'GET', ...rest } = options || {}

  const url = buildUrl(endpoint, baseUrl, params)

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // 自动添加 Authorization 头
  const token = getAccessToken()
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`
  }

  // FormData 时让浏览器自动设置 Content-Type（需要 boundary）
  if (body instanceof FormData) {
    delete defaultHeaders['Content-Type']
  }

  const config: RequestInit = {
    method,
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    ...rest,
  }

  if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    if (body instanceof FormData) {
      config.body = body
    } else if (body instanceof Blob || body instanceof ArrayBuffer || typeof body === 'string') {
      // 原始字节/文本体：透传，调用方自行指定 Content-Type
      config.body = body
    } else {
      config.body = JSON.stringify(body)
    }
  }

  try {
    const response = await fetch(url, config)

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('apm_access_token')
        localStorage.removeItem('apm_username')
        localStorage.removeItem('apm_external_token')

        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
      }

      let errorData: any = { message: `HTTP error! status: ${response.status}` }
      try {
        errorData = await response.json()
      } catch {
        // 非 JSON 格式，使用默认错误信息
      }
      throw new Error(errorData.detail || errorData.message || `API Error: ${response.status}`)
    }

    // 尝试解析 JSON，204 No Content 等返回空对象
    const text = await response.text()
    return text ? JSON.parse(text) : ({} as T)
  } catch (error) {
    console.error('API Fetch Error:', error)
    throw error
  }
}

// 封装常用 HTTP 方法
export const api = {
  get: <T>(endpoint: string, options?: ApiOptions) =>
    apiFetch<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body?: any, options?: ApiOptions) =>
    apiFetch<T>(endpoint, { ...options, method: 'POST', body }),

  put: <T>(endpoint: string, body?: any, options?: ApiOptions) =>
    apiFetch<T>(endpoint, { ...options, method: 'PUT', body }),

  patch: <T>(endpoint: string, body?: any, options?: ApiOptions) =>
    apiFetch<T>(endpoint, { ...options, method: 'PATCH', body }),

  delete: <T>(endpoint: string, options?: ApiOptions) =>
    apiFetch<T>(endpoint, { ...options, method: 'DELETE' }),
}
