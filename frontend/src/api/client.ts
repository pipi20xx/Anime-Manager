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

export async function apiFetch<T>(
  endpoint: string,
  options?: ApiOptions,
): Promise<T> {
  const { baseUrl = API_BASE_URL, params, headers, body, method = 'GET', ...rest } = options || {}

  let url = `${baseUrl}${endpoint}`

  if (params) {
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
  }

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // 自动添加 Authorization 头
  const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
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
