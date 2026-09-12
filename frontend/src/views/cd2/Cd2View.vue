<script setup lang="ts">
/**
 * Cd2View — CD2 管理
 *
 * 标签页:
 * 1. 文件浏览 - 云端目录浏览与文件操作（离线下载管理入口在账号目录内）
 * 2. 传输监控 - 后台传输监控状态与当前监控中的任务快照
 * 3. 协议管理 - clouddrive.proto 版本信息与强制更新
 */
import { ref } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import FilesTab from './FilesTab.vue'
import MonitorTab from './MonitorTab.vue'
import ProtoTab from './ProtoTab.vue'

defineOptions({ name: 'Cd2View' })

const activeTab = ref('files')

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '文件浏览', icon: 'mdi-folder-multiple-outline', tab: 'files' },
    { title: '传输监控', icon: 'mdi-transfer', tab: 'monitor' },
    { title: '协议管理', icon: 'mdi-file-code-outline', tab: 'proto' },
  ],
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <v-window-item value="files">
        <FilesTab />
      </v-window-item>
      <v-window-item value="monitor">
        <MonitorTab />
      </v-window-item>
      <v-window-item value="proto">
        <ProtoTab />
      </v-window-item>
    </v-window>
  </v-container>
</template>
