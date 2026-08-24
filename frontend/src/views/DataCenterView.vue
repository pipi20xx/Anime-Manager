<script setup lang="ts">
/**
 * DataCenterView — 数据中心 (骨架)
 *
 * 仅负责 Tab 切换，各功能模块拆分至子组件:
 * - MetadataTab: 元数据资产
 * - RulesTab: 二级分类规则
 * - MappingTab: ID映射管理
 * - SqlLabTab: SQL 实验室
 * - EngineConfigTab: 引擎配置
 * - MaintenanceTab: 维护中心
 */
import { ref } from 'vue'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import MetadataTab from './datacenter/MetadataTab.vue'
import RulesTab from './datacenter/RulesTab.vue'
import MappingTab from './datacenter/MappingTab.vue'
import SqlLabTab from './datacenter/SqlLabTab.vue'
import EngineConfigTab from './datacenter/EngineConfigTab.vue'
import MaintenanceTab from './datacenter/MaintenanceTab.vue'

defineOptions({ name: 'DataCenterView' })

const activeTab = ref('metadata')

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '元数据资产', icon: 'mdi-image-multiple-outline', tab: 'metadata' },
    { title: '二级分类规则', icon: 'mdi-tag-multiple-outline', tab: 'rules' },
    { title: 'ID映射管理', icon: 'mdi-swap-horizontal', tab: 'mapping' },
    { title: 'SQL 实验室', icon: 'mdi-code-block-braces', tab: 'sqllab' },
    { title: '引擎配置', icon: 'mdi-database-cog-outline', tab: 'dbconfig' },
    { title: '维护中心', icon: 'mdi-wrench-outline', tab: 'maintenance' },
  ],
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <v-window-item value="metadata"><MetadataTab /></v-window-item>
      <v-window-item value="rules"><RulesTab /></v-window-item>
      <v-window-item value="mapping"><MappingTab /></v-window-item>
      <v-window-item value="sqllab"><SqlLabTab /></v-window-item>
      <v-window-item value="dbconfig"><EngineConfigTab /></v-window-item>
      <v-window-item value="maintenance"><MaintenanceTab /></v-window-item>
    </v-window>
  </v-container>
</template>
