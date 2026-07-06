import { createApp } from 'vue'
import './styles/global.css'
import './styles/responsive.css'
import App from './App.vue'
import axios from 'axios'
import router from './router'

// --- 401 统一处理（防重入 + token 验证）---
// 多个并发请求可能同时返回 401，用一个标志位确保只触发一次验证/刷新
let isHandling401 = false
async function handle401(requestUrl?: string) {
    // 登录接口的 401 是密码错误，不应触发登出
    if (requestUrl && requestUrl.includes('/api/auth/login')) {
        return
    }
    if (isHandling401) return
    isHandling401 = true

    // 如果没有 token，说明已登出，无需处理
    const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
    if (!token) {
        isHandling401 = false
        return
    }

    // 验证 token 是否真的失效（后端并发锁竞争可能产生误判 401）
    try {
        const verifyRes = await axios.get('/api/auth/me', {
            headers: { Authorization: `Bearer ${token}` }
        })
        if (verifyRes.status === 200) {
            // Token 仍然有效，忽略这个 401（瞬态错误）
            console.warn('收到 401 但 token 验证通过，可能是后端并发锁竞争，已忽略')
            isHandling401 = false
            return
        }
    } catch {
        // 验证也失败，token 确实失效，继续执行登出
    }

    console.warn('认证失败 (401)，正在退出登录...')
    localStorage.removeItem('apm_access_token')
    localStorage.removeItem('apm_username')
    localStorage.removeItem('apm_external_token')
    window.location.reload()
}

// --- 全局 Axios 拦截器 ---
axios.interceptors.request.use(config => {
    const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
}, error => {
    return Promise.reject(error)
})

axios.interceptors.response.use(response => response, error => {
    if (error.response?.status === 401) {
        handle401(error.config?.url)
    }
    return Promise.reject(error)
})

// --- 全局 Fetch 拦截器 (用于 API 认证) ---
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;
    
    // 如果是 API 请求，自动注入 Token
    if (typeof resource === 'string' && resource.includes('/api/')) {
        const token = localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token');
        if (token) {
            config = config || {};
            const headers = new Headers(config.headers || {});
            if (!headers.has('Authorization')) {
                headers.set('Authorization', `Bearer ${token}`);
            }
            config.headers = headers;
        }
    }
    
    const response = await originalFetch(resource, config);
    
    // 处理 401 错误（复用统一的防重入逻辑，传入请求 URL 以排除登录接口）
    if (response.status === 401) {
        handle401(typeof resource === 'string' ? resource : undefined)
    }

    return response;
};

const app = createApp(App)

app.use(router)

// --- 全局指令：禁用自动填充 ---
app.directive('no-autocomplete', {
  mounted(el) {
    const inputs = el.querySelectorAll ? el.querySelectorAll('input') : [el]
    inputs.forEach((input: HTMLInputElement) => {
      input.setAttribute('autocomplete', 'off')
      input.setAttribute('autocorrect', 'off')
      input.setAttribute('autocapitalize', 'off')
      input.setAttribute('spellcheck', 'false')
    })
  }
})

app.mount('#app')
