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
        // Token 过期或无效
        // 可以考虑在这里跳转到登录页，但在我们的非路由架构下，
        // 我们可以通过修改 navigationStore 的状态来触发 App.vue 重新渲染
        import('./store/navigationStore').then(m => {
            m.logout()
        })
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
    
    return originalFetch(resource, config);
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
