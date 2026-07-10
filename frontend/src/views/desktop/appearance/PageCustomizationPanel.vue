<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import {
  NCard, NSlider, NSelect, NDivider, NSwitch, NTag, NButton, NPopconfirm
} from 'naive-ui'
import type { AppearanceConfig, AppearancePageConfig } from '../../../api/appearance'
import {
  customizablePageOptions,
  CUSTOMIZABLE_PAGES,
  getAppearanceKeysByPageKey,
  type CustomizablePageKey,
} from '../../../constants/appearanceKeys'
import { previewPageKey, defaultPageBackground } from '../../../store/appearanceStore'
import InstanceCustomizationPanel from './InstanceCustomizationPanel.vue'

/**
 * 自定义页面管理面板
 *
 * 让每个页面（任务中心、虚拟 STRM 库等）可以：
 * 1. 设置独立的页面级背景图与遮罩效果（覆盖全局背景）
 * 2. 设置页面级组件覆盖（输入框/搜索框/标签页/列表/按钮/卡片/文字样式）
 * 3. 管理该页面下所有弹框/卡片的单独自定义外观
 *
 * 选择页面后会设置 previewPageKey，让外观设置页面也能实时预览该页面的背景效果。
 */

const props = defineProps<{
  /** 父组件的 form 对象（reactive，会直接修改其 pages 和 instances 字段） */
  form: AppearanceConfig
  /** 背景图片选项（来自父组件加载的 images 列表） */
  imageOptions: { label: string; value: string }[]
}>()

const emit = defineEmits<{
  /** 任何配置变更后触发，让父组件调用 applyAppearanceToCss 实时预览 */
  (e: 'change'): void
}>()

const selectedPageKey = ref<CustomizablePageKey | ''>('')

/** 页面级背景默认值（从 store 导入） */
const defaultPageBg = defaultPageBackground

/** 获取当前选中页面的配置（自动初始化） */
const currentPageConfig = computed<AppearancePageConfig>(() => {
  if (!selectedPageKey.value) return { ...defaultPageBg }
  const key = selectedPageKey.value as string
  if (!props.form.pages) {
    (props.form as any).pages = {}
  }
  if (!props.form.pages[key]) {
    props.form.pages[key] = { ...defaultPageBg }
  }
  return props.form.pages[key]
})

/** 向后兼容：背景配置 */
const currentPageBg = currentPageConfig

/** 当前选中页面包含的组件数量 */
const pageComponentCount = computed(() => {
  if (!selectedPageKey.value) return 0
  return getAppearanceKeysByPageKey(selectedPageKey.value as string).length
})

/** 当前选中页面已自定义的组件数量 */
const customizedCount = computed(() => {
  if (!selectedPageKey.value || !props.form.instances) return 0
  const keys = getAppearanceKeysByPageKey(selectedPageKey.value as string)
  return keys.filter(k => props.form.instances![k]).length
})

/** 当前选中页面已覆盖的组件分类数量 */
const overriddenCategoryCount = computed(() => {
  if (!selectedPageKey.value || !props.form.pages) return 0
  const pageConfig = props.form.pages[selectedPageKey.value as string]
  if (!pageConfig?.overrides) return 0
  return Object.keys(pageConfig.overrides).length
})

/** 通知父组件预览 */
function notifyChange(): void {
  emit('change')
}

/** 选中页面变化时设置预览 key */
watch(selectedPageKey, (key) => {
  previewPageKey.value = key || null
  notifyChange()
})

/** 组件卸载时清除预览 key */
onUnmounted(() => {
  previewPageKey.value = null
})

/** 删除当前页面的背景配置 */
function deletePageBgConfig() {
  if (!selectedPageKey.value) return
  const key = selectedPageKey.value as string
  if (props.form.pages && props.form.pages[key]) {
    // 保留 overrides，只清除背景字段
    const overrides = props.form.pages[key].overrides
    props.form.pages[key] = { ...defaultPageBg, overrides }
  }
  notifyChange()
}
</script>

<template>
  <div class="page-customization">
    <!-- 页面选择器 -->
    <n-card class="app-card-config settings-section" :bordered="true">
      <div class="section-header">
        <div>
          <div class="section-title">自定义页面</div>
          <div class="section-desc">为指定页面设置独立的背景图、组件覆盖，以及管理页面内弹框/卡片的外观</div>
        </div>
      </div>
      <n-divider />
      <div class="form-row">
        <div class="form-label">选择页面</div>
        <div class="form-control">
          <n-select
            v-model:value="selectedPageKey"
            :options="customizablePageOptions"
            placeholder="选择要自定义的页面"
            style="flex: 1;"
          />
        </div>
      </div>
      <div v-if="selectedPageKey" class="page-meta">
        <div class="page-meta__label">{{ CUSTOMIZABLE_PAGES[selectedPageKey]?.label }}</div>
        <div class="page-meta__desc">{{ CUSTOMIZABLE_PAGES[selectedPageKey]?.description }}</div>
        <div class="page-meta__stats">
          <n-tag size="small" type="info">页面内 {{ pageComponentCount }} 个组件</n-tag>
          <n-tag v-if="overriddenCategoryCount > 0" size="small" type="warning">{{ overriddenCategoryCount }} 项组件覆盖</n-tag>
          <n-tag v-if="customizedCount > 0" size="small" type="success">{{ customizedCount }} 个已单独自定义</n-tag>
        </div>
      </div>
    </n-card>

    <template v-if="selectedPageKey">
      <!-- 页面全局背景设置 -->
      <n-card class="app-card-config settings-section page-bg-section" :bordered="true">
        <div class="section-header">
          <div>
            <div class="section-title">页面全局背景</div>
            <div class="section-desc">设置该页面独立的全局背景图片与遮罩效果（覆盖全局背景设置）</div>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <n-popconfirm
              v-if="currentPageBg.enabled || currentPageBg.background_image"
              @positive-click="deletePageBgConfig"
            >
              <template #trigger>
                <n-button type="error" ghost size="small">清除背景配置</n-button>
              </template>
              确定清除该页面的背景配置？将回退到全局背景。
            </n-popconfirm>
            <n-switch v-model:value="currentPageBg.enabled" @update:value="notifyChange" />
          </div>
        </div>
        <template v-if="currentPageBg.enabled">
          <n-divider />
          <div class="form-row">
            <div class="form-label">背景图片</div>
            <div class="form-control">
              <n-select
                v-model:value="currentPageBg.background_image"
                :options="imageOptions"
                @update:value="notifyChange"
                placeholder="选择背景图片"
              />
            </div>
          </div>
          <div class="form-row">
            <div class="form-label">遮罩暗化 <n-tag size="small" type="info">{{ (currentPageBg.background_overlay_opacity * 100).toFixed(0) }}%</n-tag></div>
            <div class="form-control">
              <n-slider
                v-model:value="currentPageBg.background_overlay_opacity"
                :min="0" :max="1" :step="0.05"
                @update:value="notifyChange"
              />
            </div>
          </div>
          <div class="form-row">
            <div class="form-label">背景模糊 <n-tag size="small" type="info">{{ currentPageBg.background_blur }}px</n-tag></div>
            <div class="form-control">
              <n-slider
                v-model:value="currentPageBg.background_blur"
                :min="0" :max="30" :step="1"
                @update:value="notifyChange"
              />
            </div>
          </div>
          <div class="form-row">
            <div class="form-label">布局不透明度 <n-tag size="small" type="info">{{ (currentPageBg.layout_opacity * 100).toFixed(0) }}%</n-tag></div>
            <div class="form-control">
              <n-slider
                v-model:value="currentPageBg.layout_opacity"
                :min="0.1" :max="1" :step="0.05"
                @update:value="notifyChange"
              />
            </div>
          </div>
        </template>
      </n-card>

      <!-- 页面级组件覆盖（输入框/搜索框/标签页/列表/按钮/卡片/文字样式） -->
      <InstanceCustomizationPanel
        :form="form"
        :image-options="imageOptions"
        :page-overrides-key="selectedPageKey as string"
        @change="notifyChange"
      />

      <!-- 页面内弹框/卡片单独自定义 -->
      <InstanceCustomizationPanel
        :form="form"
        :image-options="imageOptions"
        :page-key-filter="selectedPageKey as string"
        @change="notifyChange"
      />
    </template>
  </div>
</template>

<style scoped>
.page-customization {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.section-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.section-desc { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }

.form-row { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.form-row:last-child { margin-bottom: 0; }
.form-label { min-width: 130px; font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }
.form-control { flex: 1; }

.page-meta {
  padding: 12px 16px;
  background: var(--bg-surface);
  border-radius: 8px;
  border-left: 3px solid var(--n-primary-color);
  margin-top: 8px;
}
.page-meta__label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.page-meta__desc { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
.page-meta__stats { display: flex; gap: 8px; margin-top: 8px; }
</style>
