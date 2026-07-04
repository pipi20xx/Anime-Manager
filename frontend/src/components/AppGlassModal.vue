<script setup lang="ts">
import { computed } from 'vue'
import { NModal } from 'naive-ui'

/**
 * AppGlassModal - 统一的Modal封装组件
 * 
 * 功能:
 * - 统一使用 preset="card" 确保样式一致性
 * - 自动应用蓝色边框和透明遮罩样式
 * - 支持 v-bind="$attrs" 透传所有外部属性
 * - 可选的毛玻璃内容区域支持
 * 
 * 使用示例:
 * <AppGlassModal
 *   :show="show"
 *   @update:show="val => show = val"
 *   title="编辑订阅"
 *   style="width: 700px"
 * >
 *   <template #default>
 *     <n-form>...</n-form>
 *   </template>
 *   <template #action>
 *     <n-button>保存</n-button>
 *   </template>
 * </AppGlassModal>
 * 
 * 使用该组件的所有弹框表单:
 * 
 * 【订阅管理类】
 * - 新建订阅 (SubscriptionEditModalDesktop/Mobile)
 * - 编辑订阅 (SubscriptionEditModalDesktop/Mobile)
 * - 添加RSS订阅源 (FeedEditModal)
 * - 编辑RSS订阅源 (FeedEditModal)
 * - 订阅预设模板管理 (SubscriptionTemplateModalDesktop/Mobile)
 * - 订阅详情查看 (SubscriptionDetailModalDesktop)
 * - RSS订阅项列表 (FeedItemsModalDesktop)
 * - 订阅源详情 (AggregatedFeedItemsModalDesktop)
 * - 订阅过滤项填写指南 (SubscriptionHelpModal)
 * 
 * 【规则配置类】
 * - 添加匹配规则 (RssRuleModal)
 * - 编辑匹配规则 (RssRuleModal)
 * - 创建新规则/编辑重命名规则 (RuleEditModal)
 * - 添加二级分类规则 (ClassifierEditModalDesktop/Mobile)
 * - 编辑分类规则 (ClassifierEditModalDesktop/Mobile)
 * - 洗版规则管理 (PriorityRuleModalDesktop/Mobile)
 * - 编辑基础规则 (PriorityRuleModalDesktop/Mobile内部)
 * - 编辑洗版策略 (PriorityRuleModalDesktop/Mobile内部)
 * - 规则历史记录 (AggregatedRuleHistoryModalDesktop)
 * - 推送历史查看 (RuleHistoryModalDesktop/Mobile)
 * - 规则预览 (RulePreviewModalDesktop/Mobile)
 * 
 * 【下载器与客户端类】
 * - 添加下载器 (ClientEditModalDesktop/Mobile)
 * - 编辑下载器 (ClientEditModalDesktop/Mobile)
 * - Jackett补全助手 (JackettFillModal)
 * 
 * 【整理与识别类】
 * - 手动整理 (ManualOrganizeModalDesktop/Mobile)
 * - 单文件识别 (RecognitionModalDesktop/Mobile)
 * - 执行日志查看 (ExecutionLogModal)
 * - 文件选择器 (FilePickerModal)
 * - STRM任务配置 (StrmTaskModalDesktop/Mobile)
 * - 整理任务编辑 (TaskEditModalDesktop/Mobile)
 * 
 * 【系统管理类】
 * - 日志控制台 (LogConsoleModalDesktop)
 * - API外部控制中心 (ExternalControlModal)
 * - 外部控制详情 (ExternalControlDesktop)
 * - 自动RSS订阅管理 (RssDetectManagerDesktop/Mobile)
 * - RSS探测配置 (RssDetectModalDesktop/Mobile)
 * - 健康检查配置 (HealthCheckManagerDesktop/Mobile)
 * - 缓存记录编辑 (CacheViewDesktop/Mobile)
 * - 任务日志查看 (TaskHistoryViewDesktop/Mobile)
 * - 用户映射编辑 (UserMappingViewDesktop/Mobile)
 * - 设置指南 (SettingsGuide)
 * - 双重身份验证设置 (AccountTab)
 * - 队列内容查看 (ServiceStatusTab)
 * 
 * 【日历与追踪类】
 * - 日历追踪管理 (CalendarViewDesktop/Mobile)
 * - Bangumi一键订阅 (BangumiQuickSubscribeModalDesktop/Mobile)
 * - TMDB全数据查看 (TmdbFullDataViewDesktop/Mobile)
 * 
 * 总计: 55+ 个弹框表单组件已统一使用此组件
 * 所有Modal统一样式: 蓝色边框、透明遮罩、统一背景色管理
 */

const props = defineProps<{
  show: boolean
  glassContent?: boolean  // 是否对内容区域启用毛玻璃效果
  /**
   * 实例级外观 key：用于独立自定义此弹框的外观
   * 传入后会在 NModal 根元素上设置 data-app-instance 属性，
   * 配合 appearanceStore 注入的 scoped CSS 变量实现独立自定义
   * 不传则走全局默认外观
   */
  appearanceKey?: string
}>()

const emit = defineEmits(['update:show'])

// 合并后的modal样式 - 使用CSS变量支持外观自定义
const modalStyle = computed(() => ({
  maxWidth: '95vw',
}))
</script>

<template>
  <n-modal
    :show="show"
    @update:show="val => emit('update:show', val)"
    preset="card"
    :style="modalStyle"
    v-bind="$attrs"
    :data-app-instance="appearanceKey || undefined"
    :segmented="{ content: true, footer: 'soft' }"
  >
    <!-- 内容区域 - 默认不启用毛玻璃 -->
    <template #default>
      <slot />
    </template>

    <!-- 操作按钮区域 -->
    <template #action>
      <slot name="action" />
    </template>

    <!-- 其他插槽透传 -->
    <template #header>
      <slot name="header" />
    </template>
    <template #header-extra>
      <slot name="header-extra" />
    </template>
    <template #footer>
      <slot name="footer" />
    </template>
    <template #icon>
      <slot name="icon" />
    </template>
  </n-modal>
</template>

<style scoped>
/* Modal样式由global.css统一管理,这里不添加额外样式 */
</style>