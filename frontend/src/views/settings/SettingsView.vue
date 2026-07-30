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
import BasicConfigTab from './BasicConfigTab.vue'
import ClientManageTab from './ClientManageTab.vue'
import RulesConfigTab from './RulesConfigTab.vue'
import AccountTab from './AccountTab.vue'
import ServiceStatusTab from './ServiceStatusTab.vue'
import HealthCheckTab from './HealthCheckTab.vue'

defineOptions({ name: 'SettingsView' })

const activeTab = ref('basic')
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="app-page-header mb-6">
      <h1 class="text-h5 font-weight-bold">系统设置</h1>
      <div class="text-body-2 text-medium-emphasis mt-1">系统配置与选项</div>
    </div>

    <div class="sticky-tabs">
      <v-tabs v-model="activeTab" color="primary">
        <v-tab value="basic">
          <v-icon start size="18">mdi-cog-outline</v-icon>
          基础配置
        </v-tab>
        <v-tab value="clients">
          <v-icon start size="18">mdi-download-circle-outline</v-icon>
          下载器管理
        </v-tab>
        <v-tab value="rules">
          <v-icon start size="18">mdi-ruler-square</v-icon>
          识别与订阅规则
        </v-tab>
        <v-tab value="account">
          <v-icon start size="18">mdi-shield-account-outline</v-icon>
          账号与安全
        </v-tab>
        <v-tab value="services">
          <v-icon start size="18">mdi-server-outline</v-icon>
          服务状态
        </v-tab>
        <v-tab value="health">
          <v-icon start size="18">mdi-harddisk-remove</v-icon>
          掉盘与失效检测
        </v-tab>
      </v-tabs>
    </div>

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
