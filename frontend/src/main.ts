import { createApp } from 'vue'
import { createPinia } from 'pinia'
import vuetify from './plugins/vuetify'
import i18n from './plugins/i18n'
import App from './App.vue'
import router from './router'

// 全局样式（按功能拆分）
import '@/styles/index.css'

const app = createApp(App)

app.use(createPinia())
app.use(vuetify)
app.use(i18n)
app.use(router)

app.mount('#app')
