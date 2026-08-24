<script setup lang="ts">
/**
 * SettingsView — 系统设置
 *
 * 标签页（与旧前端一致）:
 * 1. 基础配置 - TMDB/Bangumi/SYTMDB/识别偏好/Jackett/Emby/Telegram/代理/自动化
 * 2. 下载器管理 - 下载客户端CRUD
 * 3. 识别与订阅规则 - 识别词/制作组/渲染词/特权规则
 * 4. AI 实验室 - 独立页面（跳转至 /ai-lab）
 * 5. 账号与安全 - 密码修改/2FA/会话管理
 * 6. 服务状态 - 系统服务/文件监控/运行时统计/规则统计
 * 7. 掉盘与失效检测 - 健康检查配置
 */
import { ref } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import BasicConfigTab from './BasicConfigTab.vue'
import ClientManageTab from './ClientManageTab.vue'
import RulesConfigTab from './RulesConfigTab.vue'
import AccountTab from './AccountTab.vue'
import ServiceStatusTab from './ServiceStatusTab.vue'
import HealthCheckTab from './HealthCheckTab.vue'

defineOptions({ name: 'SettingsView' })

const activeTab = ref('basic')

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '基础配置', icon: 'mdi-cog-outline', tab: 'basic' },
    { title: '下载器管理', icon: 'mdi-download-circle-outline', tab: 'clients' },
    { title: '识别与订阅规则', icon: 'mdi-ruler-square', tab: 'rules' },
    { title: '账号与安全', icon: 'mdi-shield-account-outline', tab: 'account' },
    { title: '服务状态', icon: 'mdi-server-outline', tab: 'services' },
    { title: '掉盘与失效检测', icon: 'mdi-harddisk-remove', tab: 'health' },
  ],
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <v-window-item value="basic">
        <BasicConfigTab />
      </v-window-item>
      <v-window-item value="clients">
        <ClientManageTab />
      </v-window-item>
      <v-window-item value="rules">
        <RulesConfigTab />
      </v-window-item>
      <v-window-item value="account">
        <AccountTab />
      </v-window-item>
      <v-window-item value="services">
        <ServiceStatusTab />
      </v-window-item>
      <v-window-item value="health">
        <HealthCheckTab />
      </v-window-item>
    </v-window>
  </v-container>
</template>
