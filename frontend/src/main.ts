import { createApp } from 'vue'
import './styles/global.css'
import './styles/mobile-base.css'
import App from './App.vue'
import axios from 'axios'

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
        // Token 过期或无效，强制退出登录
        console.warn('认证失败 (401)，正在退出登录...')
        
        // 清除所有认证相关的存储
        localStorage.removeItem('apm_access_token')
        localStorage.removeItem('apm_username')
        localStorage.removeItem('apm_external_token')
        
        // 重新加载页面以触发登录界面
        window.location.reload()
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
    
    // 处理 401 错误
    if (response.status === 401) {
        console.warn('认证失败 (401)，正在退出登录...')
        localStorage.removeItem('apm_access_token')
        localStorage.removeItem('apm_username')
        localStorage.removeItem('apm_external_token')
        window.location.reload()
    }
    
    return response;
};

const app = createApp(App)

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
