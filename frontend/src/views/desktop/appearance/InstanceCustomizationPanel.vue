<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NCard, NSlider, NColorPicker, NButton, NSpace, NSelect, NDivider,
  NPopconfirm, NTag, NTabs, NTabPane, NCheckbox, NEmpty, NInput
} from 'naive-ui'
import type { AppearanceConfig, AppearanceInstanceOverrides } from '../../../api/appearance'
import {
  appearanceKeyGroupedOptions,
  getAppearanceKeyMeta,
  APPEARANCE_KEYS,
  type AppearanceKey
} from '../../../constants/appearanceKeys'

/**
 * 单独自定义组件管理面板（弹框/卡片通用）
 *
 * 让指定组件（声明了 appearance-key 的）可以独立配置外观，
 * 未配置的字段自动继承全局默认。
 *
 * 通过 v-model 形式操作父组件传入的 form.instances，
 * 任何修改都会触发 preview 事件让父组件实时应用预览。
 *
 * 通过 pageFilter prop 控制显示哪些组件：
 * - 不传：显示所有非"卡片"类型的 key（即弹框）
 * - 传 '卡片'：只显示卡片类型的 key
 */

const props = defineProps<{
  /** 父组件的 form 对象（reactive，会直接修改其 instances 字段） */
  form: AppearanceConfig
  /** 背景图片选项（来自父组件加载的 images 列表） */
  imageOptions: { label: string; value: string }[]
  /** 按 page 过滤：传 '卡片' 只显示卡片，不传显示所有非卡片 */
  pageFilter?: string
}>()

const emit = defineEmits<{
  /** 任何配置变更后触发，让父组件调用 applyAppearanceToCss 实时预览 */
  (e: 'change'): void
}>()

const selectedInstanceKey = ref<AppearanceKey | ''>('')

/** 文字样式默认值：仅实例级覆盖，全局默认不做此配置 */
const textDefaults = {
  color: '#ffffff',
  secondary_color: 'rgba(255, 255, 255, 0.7)',
  tertiary_color: 'rgba(255, 255, 255, 0.5)',
  tint_color: '#ffffff',
  input_color: '#ffffff',
  shadow: '0 2px 4px rgba(0, 0, 0, 0.5)',
  secondary_shadow: 'none',
  tertiary_shadow: 'none',
  tint_shadow: 'none',
  input_shadow: 'none',
  font_weight: 400,
  font_size: 14,
}

/**
 * 实例级专用边框字段默认值：全局默认不做边框样式配置，
 * 仅在单独自定义弹框/卡片中支持。
 * 默认值与 global.css 中 :root 的初始值保持一致。
 */
const instanceOnlyDefaults: Record<string, Record<string, any>> = {
  card: { border_color: 'rgba(255, 255, 255, 0.08)', border_width: 1, border_style: 'solid' },
  input: { border_color: 'rgba(255, 255, 255, 0.12)', border_width: 1, border_style: 'solid' },
  search: { border_color: 'rgba(255, 255, 255, 0.08)', border_width: 1, border_style: 'solid' },
  list: { border_color: 'rgba(255, 255, 255, 0.08)', border_width: 1, border_style: 'solid' },
  tabs: { border_color: 'rgba(255, 255, 255, 0.08)', border_width: 1, border_style: 'solid' },
}

/** 边框样式下拉选项 */
const borderStyleOptions = [
  { label: '实线 (solid)', value: 'solid' },
  { label: '虚线 (dashed)', value: 'dashed' },
  { label: '点线 (dotted)', value: 'dotted' },
  { label: '双线 (double)', value: 'double' },
  { label: '凹槽 (groove)', value: 'groove' },
  { label: '凸脊 (ridge)', value: 'ridge' },
  { label: '内陷 (inset)', value: 'inset' },
  { label: '外凸 (outset)', value: 'outset' },
  { label: '无边框 (none)', value: 'none' },
]

/** 判断字段是否为实例级专用字段（不存在于全局配置中） */
function isInstanceOnlyField(category: string, field: string): boolean {
  return !!(instanceOnlyDefaults[category] && field in instanceOnlyDefaults[category])
}

/** 获取实例级专用字段的默认值 */
function getInstanceOnlyDefault(category: string, field: string): any {
  return instanceOnlyDefaults[category]?.[field]
}

/** 根据 pageFilter 过滤后的下拉选项 */
const filteredOptions = computed(() => {
  if (props.pageFilter) {
    // 只显示指定 page 的 key
    const groups: Record<string, { label: string; value: string }[]> = {}
    for (const [value, meta] of Object.entries(APPEARANCE_KEYS)) {
      if (meta.page !== props.pageFilter) continue
      if (!groups[meta.page]) groups[meta.page] = []
      groups[meta.page].push({ label: meta.label, value })
    }
    return Object.entries(groups).map(([page, items]) => ({
      type: 'group' as const,
      label: page,
      key: page,
      children: items,
    }))
  } else {
    // 不传 pageFilter：显示所有非"卡片"类型的 key
    return appearanceKeyGroupedOptions.filter(g => g.label !== '卡片')
  }
})

/** 当前项目类型文字（"弹框"或"卡片"） */
const itemTypeText = computed(() => props.pageFilter === '卡片' ? '卡片' : '弹框')

/** 当前选中实例的覆盖对象（只读视图，不创建副作用） */
const currentInstanceOverrides = computed<AppearanceInstanceOverrides>(() => {
  if (!selectedInstanceKey.value) return {}
  return props.form.instances![selectedInstanceKey.value] || {}
})

/** 已存在自定义配置的实例数量（按 pageFilter 过滤，避免弹框/卡片计数混在一起） */
const instanceCount = computed(() => {
  if (!props.form.instances) return 0
  return Object.keys(props.form.instances).filter(key => {
    const meta = getAppearanceKeyMeta(key)
    if (!meta) return false
    // 与 filteredOptions 的过滤逻辑保持一致：
    //   pageFilter 存在 → 只统计该 page 的实例（如 '卡片'）
    //   pageFilter 不存在 → 统计所有非 '卡片' 的实例（即弹框）
    if (props.pageFilter) {
      return meta.page === props.pageFilter
    }
    return meta.page !== '卡片'
  }).length
})

/** 通知父组件预览 */
function notifyChange(): void {
  emit('change')
}

/** 判断某字段是否已被覆盖（!== undefined 视为覆盖） */
function isFieldOverridden(category: keyof AppearanceInstanceOverrides, field: string): boolean {
  if (!selectedInstanceKey.value) return false
  const inst = props.form.instances![selectedInstanceKey.value]
  if (!inst || !inst[category]) return false
  return (inst[category] as Record<string, any>)[field] !== undefined
}

/** 启用字段覆盖：用当前全局值作为初始值（文字样式/边框样式字段使用内置默认值） */
function enableFieldOverride(category: keyof AppearanceInstanceOverrides, field: string): void {
  if (!selectedInstanceKey.value) return
  const key = selectedInstanceKey.value
  if (!props.form.instances![key]) props.form.instances![key] = {}
  if (!props.form.instances![key][category]) {
    ;(props.form.instances![key] as any)[category] = {}
  }
  if (category === 'text') {
    ;(props.form.instances![key][category] as Record<string, any>)[field] = (textDefaults as Record<string, any>)[field]
  } else if (isInstanceOnlyField(category, field)) {
    ;(props.form.instances![key][category] as Record<string, any>)[field] = getInstanceOnlyDefault(category, field)
  } else {
    ;(props.form.instances![key][category] as Record<string, any>)[field] = (props.form[category] as any)[field]
  }
  notifyChange()
}

/** 取消字段覆盖：删除字段 */
function clearFieldOverride(category: keyof AppearanceInstanceOverrides, field: string): void {
  if (!selectedInstanceKey.value) return
  const key = selectedInstanceKey.value
  if (!props.form.instances![key] || !props.form.instances![key][category]) return
  delete (props.form.instances![key][category] as Record<string, any>)[field]
  // 如果该分区已无任何覆盖，删除整个分区对象
  if (Object.keys(props.form.instances![key][category] as object).length === 0) {
    delete (props.form.instances![key] as any)[category]
  }
  // 如果该实例已无任何覆盖，删除整个实例
  if (Object.keys(props.form.instances![key]).length === 0) {
    delete props.form.instances![key]
  }
  notifyChange()
}

/** 切换字段覆盖状态 */
function toggleFieldOverride(category: keyof AppearanceInstanceOverrides, field: string, checked: boolean): void {
  if (checked) {
    enableFieldOverride(category, field)
  } else {
    clearFieldOverride(category, field)
  }
}

/** 获取字段值（覆盖值优先，未覆盖则返回全局值；文字样式/边框样式字段返回内置默认值） */
function getFieldValue(category: keyof AppearanceInstanceOverrides, field: string): any {
  if (!selectedInstanceKey.value) {
    if (category === 'text') return (textDefaults as Record<string, any>)[field]
    if (isInstanceOnlyField(category, field)) return getInstanceOnlyDefault(category, field)
    return (props.form[category] as any)[field]
  }
  const inst = props.form.instances![selectedInstanceKey.value]
  if (inst && inst[category] && (inst[category] as Record<string, any>)[field] !== undefined) {
    return (inst[category] as Record<string, any>)[field]
  }
  if (category === 'text') return (textDefaults as Record<string, any>)[field]
  if (isInstanceOnlyField(category, field)) return getInstanceOnlyDefault(category, field)
  return (props.form[category] as any)[field]
}

/** 设置字段值（直接设置到 instances 中） */
function setFieldValue(category: keyof AppearanceInstanceOverrides, field: string, value: any): void {
  if (!selectedInstanceKey.value) return
  const key = selectedInstanceKey.value
  if (!props.form.instances![key]) props.form.instances![key] = {}
  if (!props.form.instances![key][category]) {
    ;(props.form.instances![key] as any)[category] = {}
  }
  ;(props.form.instances![key][category] as Record<string, any>)[field] = value
  notifyChange()
}

/** 删除整个实例的自定义配置 */
function deleteInstanceConfig(key: string): void {
  delete props.form.instances![key]
  if (selectedInstanceKey.value === key) {
    selectedInstanceKey.value = ''
  }
  notifyChange()
}

defineExpose({ currentInstanceOverrides, instanceCount })
</script>

<template>
  <n-card class="app-card-config settings-section instance-section" :bordered="true">
    <div class="section-header">
      <div>
        <div class="section-title">
          单独自定义{{ itemTypeText }}
          <n-tag v-if="instanceCount > 0" size="small" type="success" style="margin-left: 8px;">{{ instanceCount }} 个已自定义</n-tag>
        </div>
        <div class="section-desc">为指定的{{ itemTypeText }}设置独立外观，未配置的{{ itemTypeText }}走全局默认</div>
      </div>
    </div>

    <n-divider />

    <!-- 选择要配置的弹框 -->
    <div class="form-row">
      <div class="form-label">{{ pageFilter === '卡片' ? '选择卡片' : '选择弹框' }}</div>
      <div class="form-control" style="display: flex; gap: 8px; align-items: center;">
        <n-select
          v-model:value="selectedInstanceKey"
          :options="filteredOptions"
          :placeholder="pageFilter === '卡片' ? '选择要单独自定义的卡片' : '选择要单独自定义的弹框'"
          style="flex: 1;"
        />
        <n-popconfirm
          v-if="selectedInstanceKey && form.instances![selectedInstanceKey]"
          @positive-click="deleteInstanceConfig(selectedInstanceKey)"
        >
          <template #trigger>
            <n-button type="error" ghost>清除该{{ itemTypeText }}配置</n-button>
          </template>
          确定清除该{{ itemTypeText }}的所有自定义配置？将回退到全局默认。
        </n-popconfirm>
      </div>
    </div>

    <!-- 选中实例后的配置面板 -->
    <template v-if="selectedInstanceKey">
      <div class="instance-meta" v-if="getAppearanceKeyMeta(selectedInstanceKey)">
        <div class="instance-meta__page">{{ getAppearanceKeyMeta(selectedInstanceKey)?.page }}</div>
        <div class="instance-meta__title">{{ getAppearanceKeyMeta(selectedInstanceKey)?.label }}</div>
        <div class="instance-meta__desc">{{ getAppearanceKeyMeta(selectedInstanceKey)?.description }}</div>
        <div class="instance-meta__key">key: <code>{{ selectedInstanceKey }}</code></div>
      </div>

      <n-tabs type="line" animated style="margin-top: 16px; --tabs-pane-padding: 16px 0 0 0;">
        <!-- 弹框本身分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('modal')" name="modal" tab="弹框本身">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'background_image')" @update:checked="v => toggleFieldOverride('modal', 'background_image', v)">背景图片</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'background_image')" class="instance-field__control">
                <n-select
                  :value="getFieldValue('modal', 'background_image')"
                  :options="imageOptions"
                  placeholder="选择背景图片"
                  @update:value="v => setFieldValue('modal', 'background_image', v)"
                />
              </div>
              <div v-else class="instance-field__hint">继承全局</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'background_blur')" @update:checked="v => toggleFieldOverride('modal', 'background_blur', v)">背景模糊</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'background_blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('modal', 'background_blur')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('modal', 'background_blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('modal', 'background_blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.modal.background_blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'background_opacity')" @update:checked="v => toggleFieldOverride('modal', 'background_opacity', v)">背景不透明度</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'background_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('modal', 'background_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('modal', 'background_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('modal', 'background_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.modal.background_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'background_overlay_opacity')" @update:checked="v => toggleFieldOverride('modal', 'background_overlay_opacity', v)">遮罩暗化</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'background_overlay_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('modal', 'background_overlay_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('modal', 'background_overlay_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('modal', 'background_overlay_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.modal.background_overlay_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'border_color')" @update:checked="v => toggleFieldOverride('modal', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('modal', 'border_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('modal', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.modal.border_color }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'border_width')" @update:checked="v => toggleFieldOverride('modal', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('modal', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('modal', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('modal', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.modal.border_width }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('modal', 'border_radius')" @update:checked="v => toggleFieldOverride('modal', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('modal', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('modal', 'border_radius')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('modal', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('modal', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.modal.border_radius }}px</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 输入框分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('input')" name="input" tab="输入框">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'bg_opacity')" @update:checked="v => toggleFieldOverride('input', 'bg_opacity', v)">背景不透明度</n-checkbox>
              <div v-if="isFieldOverridden('input', 'bg_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('input', 'bg_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('input', 'bg_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('input', 'bg_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.input.bg_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'border_radius')" @update:checked="v => toggleFieldOverride('input', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('input', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('input', 'border_radius')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('input', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('input', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.input.border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'height')" @update:checked="v => toggleFieldOverride('input', 'height', v)">高度</n-checkbox>
              <div v-if="isFieldOverridden('input', 'height')" class="instance-field__control">
                <n-slider :value="getFieldValue('input', 'height')" :min="36" :max="72" :step="2" @update:value="v => setFieldValue('input', 'height', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('input', 'height') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.input.height }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'blur')" @update:checked="v => toggleFieldOverride('input', 'blur', v)">背景模糊</n-checkbox>
              <div v-if="isFieldOverridden('input', 'blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('input', 'blur')" :min="0" :max="20" :step="1" @update:value="v => setFieldValue('input', 'blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('input', 'blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.input.blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'border_color')" @update:checked="v => toggleFieldOverride('input', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('input', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('input', 'border_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('input', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'border_width')" @update:checked="v => toggleFieldOverride('input', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('input', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('input', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('input', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('input', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('input', 'border_style')" @update:checked="v => toggleFieldOverride('input', 'border_style', v)">边框样式</n-checkbox>
              <div v-if="isFieldOverridden('input', 'border_style')" class="instance-field__control">
                <n-select :value="getFieldValue('input', 'border_style')" :options="borderStyleOptions" size="small" @update:value="v => setFieldValue('input', 'border_style', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 搜索框分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('search')" name="search" tab="搜索框">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'bg_opacity')" @update:checked="v => toggleFieldOverride('search', 'bg_opacity', v)">背景不透明度</n-checkbox>
              <div v-if="isFieldOverridden('search', 'bg_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('search', 'bg_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('search', 'bg_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('search', 'bg_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.search.bg_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'border_radius')" @update:checked="v => toggleFieldOverride('search', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('search', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('search', 'border_radius')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('search', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('search', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.search.border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'height')" @update:checked="v => toggleFieldOverride('search', 'height', v)">高度</n-checkbox>
              <div v-if="isFieldOverridden('search', 'height')" class="instance-field__control">
                <n-slider :value="getFieldValue('search', 'height')" :min="32" :max="60" :step="2" @update:value="v => setFieldValue('search', 'height', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('search', 'height') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.search.height }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'blur')" @update:checked="v => toggleFieldOverride('search', 'blur', v)">背景模糊</n-checkbox>
              <div v-if="isFieldOverridden('search', 'blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('search', 'blur')" :min="0" :max="20" :step="1" @update:value="v => setFieldValue('search', 'blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('search', 'blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.search.blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'border_color')" @update:checked="v => toggleFieldOverride('search', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('search', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('search', 'border_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('search', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'border_width')" @update:checked="v => toggleFieldOverride('search', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('search', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('search', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('search', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('search', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('search', 'border_style')" @update:checked="v => toggleFieldOverride('search', 'border_style', v)">边框样式</n-checkbox>
              <div v-if="isFieldOverridden('search', 'border_style')" class="instance-field__control">
                <n-select :value="getFieldValue('search', 'border_style')" :options="borderStyleOptions" size="small" @update:value="v => setFieldValue('search', 'border_style', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 标签页外观分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('tabs')" name="tabs" tab="标签页外观">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'nav_blur')" @update:checked="v => toggleFieldOverride('tabs', 'nav_blur', v)">导航栏模糊</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'nav_blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'nav_blur')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('tabs', 'nav_blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'nav_blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.nav_blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'nav_opacity')" @update:checked="v => toggleFieldOverride('tabs', 'nav_opacity', v)">导航栏不透明度</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'nav_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'nav_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('tabs', 'nav_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('tabs', 'nav_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.tabs.nav_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_active_bg')" @update:checked="v => toggleFieldOverride('tabs', 'tab_active_bg', v)">激活标签背景色</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_active_bg')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('tabs', 'tab_active_bg')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('tabs', 'tab_active_bg', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_active_bg }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_active_text_color')" @update:checked="v => toggleFieldOverride('tabs', 'tab_active_text_color', v)">激活标签文字色</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_active_text_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('tabs', 'tab_active_text_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('tabs', 'tab_active_text_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_active_text_color }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_height')" @update:checked="v => toggleFieldOverride('tabs', 'tab_height', v)">标签高度</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_height')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'tab_height')" :min="28" :max="72" :step="2" @update:value="v => setFieldValue('tabs', 'tab_height', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'tab_height') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_height }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_gap')" @update:checked="v => toggleFieldOverride('tabs', 'tab_gap', v)">标签间距</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_gap')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'tab_gap')" :min="0" :max="24" :step="1" @update:value="v => setFieldValue('tabs', 'tab_gap', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'tab_gap') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_gap }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_padding')" @update:checked="v => toggleFieldOverride('tabs', 'tab_padding', v)">标签内边距</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_padding')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'tab_padding')" :min="1" :max="40" :step="1" @update:value="v => setFieldValue('tabs', 'tab_padding', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'tab_padding') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_padding }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_border_radius')" @update:checked="v => toggleFieldOverride('tabs', 'tab_border_radius', v)">标签圆角</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'tab_border_radius')" :min="0" :max="24" :step="1" @update:value="v => setFieldValue('tabs', 'tab_border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'tab_border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'tab_font_size')" @update:checked="v => toggleFieldOverride('tabs', 'tab_font_size', v)">标签文字大小</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'tab_font_size')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'tab_font_size')" :min="10" :max="20" :step="1" @update:value="v => setFieldValue('tabs', 'tab_font_size', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'tab_font_size') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.tabs.tab_font_size }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'border_color')" @update:checked="v => toggleFieldOverride('tabs', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('tabs', 'border_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('tabs', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'border_width')" @update:checked="v => toggleFieldOverride('tabs', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('tabs', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('tabs', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('tabs', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('tabs', 'border_style')" @update:checked="v => toggleFieldOverride('tabs', 'border_style', v)">边框样式</n-checkbox>
              <div v-if="isFieldOverridden('tabs', 'border_style')" class="instance-field__control">
                <n-select :value="getFieldValue('tabs', 'border_style')" :options="borderStyleOptions" size="small" @update:value="v => setFieldValue('tabs', 'border_style', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 卡片分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('card')" name="card" tab="卡片">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'background_image')" @update:checked="v => toggleFieldOverride('card', 'background_image', v)">背景图片</n-checkbox>
              <div v-if="isFieldOverridden('card', 'background_image')" class="instance-field__control">
                <n-select
                  :value="getFieldValue('card', 'background_image')"
                  :options="imageOptions"
                  placeholder="选择背景图片"
                  @update:value="v => setFieldValue('card', 'background_image', v)"
                />
              </div>
              <div v-else class="instance-field__hint">继承全局</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'background_opacity')" @update:checked="v => toggleFieldOverride('card', 'background_opacity', v)">背景不透明度</n-checkbox>
              <div v-if="isFieldOverridden('card', 'background_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('card', 'background_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('card', 'background_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('card', 'background_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.card.background_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'border_radius')" @update:checked="v => toggleFieldOverride('card', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('card', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('card', 'border_radius')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('card', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('card', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.card.border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'blur')" @update:checked="v => toggleFieldOverride('card', 'blur', v)">背景模糊</n-checkbox>
              <div v-if="isFieldOverridden('card', 'blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('card', 'blur')" :min="0" :max="20" :step="1" @update:value="v => setFieldValue('card', 'blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('card', 'blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.card.blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'border_color')" @update:checked="v => toggleFieldOverride('card', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('card', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('card', 'border_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('card', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'border_width')" @update:checked="v => toggleFieldOverride('card', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('card', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('card', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('card', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('card', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('card', 'border_style')" @update:checked="v => toggleFieldOverride('card', 'border_style', v)">边框样式</n-checkbox>
              <div v-if="isFieldOverridden('card', 'border_style')" class="instance-field__control">
                <n-select :value="getFieldValue('card', 'border_style')" :options="borderStyleOptions" size="small" @update:value="v => setFieldValue('card', 'border_style', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 文字样式分区（仅实例级，全局默认不做） -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('modal') || getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('card')" name="text" tab="文字样式">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'color')" @update:checked="v => toggleFieldOverride('text', 'color', v)">文字主色</n-checkbox>
              <div v-if="isFieldOverridden('text', 'color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('text', 'color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('text', 'color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'secondary_color')" @update:checked="v => toggleFieldOverride('text', 'secondary_color', v)">次要文字色</n-checkbox>
              <div v-if="isFieldOverridden('text', 'secondary_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('text', 'secondary_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('text', 'secondary_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'tertiary_color')" @update:checked="v => toggleFieldOverride('text', 'tertiary_color', v)">第三文字色</n-checkbox>
              <div v-if="isFieldOverridden('text', 'tertiary_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('text', 'tertiary_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('text', 'tertiary_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'tint_color')" @update:checked="v => toggleFieldOverride('text', 'tint_color', v)">彩色底色文字色</n-checkbox>
              <div v-if="isFieldOverridden('text', 'tint_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('text', 'tint_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('text', 'tint_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'input_color')" @update:checked="v => toggleFieldOverride('text', 'input_color', v)">输入框文字色</n-checkbox>
              <div v-if="isFieldOverridden('text', 'input_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('text', 'input_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('text', 'input_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'shadow')" @update:checked="v => toggleFieldOverride('text', 'shadow', v)">主字阴影</n-checkbox>
              <div v-if="isFieldOverridden('text', 'shadow')" class="instance-field__control">
                <n-input :value="getFieldValue('text', 'shadow')" placeholder="例如：0 2px 4px rgba(0,0,0,0.5)" @update:value="v => setFieldValue('text', 'shadow', v)" size="small" style="flex: 1;" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'secondary_shadow')" @update:checked="v => toggleFieldOverride('text', 'secondary_shadow', v)">次要文字色阴影</n-checkbox>
              <div v-if="isFieldOverridden('text', 'secondary_shadow')" class="instance-field__control">
                <n-input :value="getFieldValue('text', 'secondary_shadow')" placeholder="例如：0 1px 2px rgba(0,0,0,0.3)" @update:value="v => setFieldValue('text', 'secondary_shadow', v)" size="small" style="flex: 1;" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'tertiary_shadow')" @update:checked="v => toggleFieldOverride('text', 'tertiary_shadow', v)">第三文字色阴影</n-checkbox>
              <div v-if="isFieldOverridden('text', 'tertiary_shadow')" class="instance-field__control">
                <n-input :value="getFieldValue('text', 'tertiary_shadow')" placeholder="例如：0 1px 2px rgba(0,0,0,0.3)" @update:value="v => setFieldValue('text', 'tertiary_shadow', v)" size="small" style="flex: 1;" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'tint_shadow')" @update:checked="v => toggleFieldOverride('text', 'tint_shadow', v)">彩色底色文字阴影</n-checkbox>
              <div v-if="isFieldOverridden('text', 'tint_shadow')" class="instance-field__control">
                <n-input :value="getFieldValue('text', 'tint_shadow')" placeholder="例如：0 1px 2px rgba(0,0,0,0.3)" @update:value="v => setFieldValue('text', 'tint_shadow', v)" size="small" style="flex: 1;" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'input_shadow')" @update:checked="v => toggleFieldOverride('text', 'input_shadow', v)">输入框文字阴影</n-checkbox>
              <div v-if="isFieldOverridden('text', 'input_shadow')" class="instance-field__control">
                <n-input :value="getFieldValue('text', 'input_shadow')" placeholder="例如：0 1px 2px rgba(0,0,0,0.3)" @update:value="v => setFieldValue('text', 'input_shadow', v)" size="small" style="flex: 1;" />
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'font_weight')" @update:checked="v => toggleFieldOverride('text', 'font_weight', v)">字重</n-checkbox>
              <div v-if="isFieldOverridden('text', 'font_weight')" class="instance-field__control">
                <n-slider :value="getFieldValue('text', 'font_weight')" :min="100" :max="900" :step="100" @update:value="v => setFieldValue('text', 'font_weight', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('text', 'font_weight') }}</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('text', 'font_size')" @update:checked="v => toggleFieldOverride('text', 'font_size', v)">字号</n-checkbox>
              <div v-if="isFieldOverridden('text', 'font_size')" class="instance-field__control">
                <n-slider :value="getFieldValue('text', 'font_size')" :min="12" :max="24" :step="1" @update:value="v => setFieldValue('text', 'font_size', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('text', 'font_size') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认主题</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 列表分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('list')" name="list" tab="列表">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'bg_opacity')" @update:checked="v => toggleFieldOverride('list', 'bg_opacity', v)">背景不透明度</n-checkbox>
              <div v-if="isFieldOverridden('list', 'bg_opacity')" class="instance-field__control">
                <n-slider :value="getFieldValue('list', 'bg_opacity')" :min="0" :max="1" :step="0.05" @update:value="v => setFieldValue('list', 'bg_opacity', v)" />
                <n-tag size="small" type="info">{{ (getFieldValue('list', 'bg_opacity') * 100).toFixed(0) }}%</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ (form.list.bg_opacity * 100).toFixed(0) }}%</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'border_radius')" @update:checked="v => toggleFieldOverride('list', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('list', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('list', 'border_radius')" :min="0" :max="20" :step="1" @update:value="v => setFieldValue('list', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('list', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.list.border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'blur')" @update:checked="v => toggleFieldOverride('list', 'blur', v)">背景模糊</n-checkbox>
              <div v-if="isFieldOverridden('list', 'blur')" class="instance-field__control">
                <n-slider :value="getFieldValue('list', 'blur')" :min="0" :max="20" :step="1" @update:value="v => setFieldValue('list', 'blur', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('list', 'blur') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.list.blur }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'border_color')" @update:checked="v => toggleFieldOverride('list', 'border_color', v)">边框颜色</n-checkbox>
              <div v-if="isFieldOverridden('list', 'border_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('list', 'border_color')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('list', 'border_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'border_width')" @update:checked="v => toggleFieldOverride('list', 'border_width', v)">边框宽度</n-checkbox>
              <div v-if="isFieldOverridden('list', 'border_width')" class="instance-field__control">
                <n-slider :value="getFieldValue('list', 'border_width')" :min="0" :max="5" :step="1" @update:value="v => setFieldValue('list', 'border_width', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('list', 'border_width') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('list', 'border_style')" @update:checked="v => toggleFieldOverride('list', 'border_style', v)">边框样式</n-checkbox>
              <div v-if="isFieldOverridden('list', 'border_style')" class="instance-field__control">
                <n-select :value="getFieldValue('list', 'border_style')" :options="borderStyleOptions" size="small" @update:value="v => setFieldValue('list', 'border_style', v)" />
              </div>
              <div v-else class="instance-field__hint">继承默认</div>
            </div>
          </div>
        </n-tab-pane>

        <!-- 按钮分区 -->
        <n-tab-pane v-if="getAppearanceKeyMeta(selectedInstanceKey)?.categories.includes('button')" name="button" tab="按钮">
          <div class="instance-fields">
            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'border_radius')" @update:checked="v => toggleFieldOverride('button', 'border_radius', v)">圆角</n-checkbox>
              <div v-if="isFieldOverridden('button', 'border_radius')" class="instance-field__control">
                <n-slider :value="getFieldValue('button', 'border_radius')" :min="0" :max="30" :step="1" @update:value="v => setFieldValue('button', 'border_radius', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('button', 'border_radius') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.border_radius }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'height_medium')" @update:checked="v => toggleFieldOverride('button', 'height_medium', v)">中等高度</n-checkbox>
              <div v-if="isFieldOverridden('button', 'height_medium')" class="instance-field__control">
                <n-slider :value="getFieldValue('button', 'height_medium')" :min="20" :max="72" :step="2" @update:value="v => setFieldValue('button', 'height_medium', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('button', 'height_medium') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.height_medium }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'height_small')" @update:checked="v => toggleFieldOverride('button', 'height_small', v)">小号高度</n-checkbox>
              <div v-if="isFieldOverridden('button', 'height_small')" class="instance-field__control">
                <n-slider :value="getFieldValue('button', 'height_small')" :min="20" :max="72" :step="2" @update:value="v => setFieldValue('button', 'height_small', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('button', 'height_small') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.height_small }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'height_tiny')" @update:checked="v => toggleFieldOverride('button', 'height_tiny', v)">超小高度</n-checkbox>
              <div v-if="isFieldOverridden('button', 'height_tiny')" class="instance-field__control">
                <n-slider :value="getFieldValue('button', 'height_tiny')" :min="16" :max="72" :step="2" @update:value="v => setFieldValue('button', 'height_tiny', v)" />
                <n-tag size="small" type="info">{{ getFieldValue('button', 'height_tiny') }}px</n-tag>
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.height_tiny }}px</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'text_color')" @update:checked="v => toggleFieldOverride('button', 'text_color', v)">纯文字按钮颜色</n-checkbox>
              <div v-if="isFieldOverridden('button', 'text_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('button', 'text_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('button', 'text_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.text_color }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'text_bg_hover')" @update:checked="v => toggleFieldOverride('button', 'text_bg_hover', v)">文字按钮 hover 底色</n-checkbox>
              <div v-if="isFieldOverridden('button', 'text_bg_hover')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('button', 'text_bg_hover')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('button', 'text_bg_hover', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.text_bg_hover }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'text_bg_pressed')" @update:checked="v => toggleFieldOverride('button', 'text_bg_pressed', v)">文字按钮 pressed 底色</n-checkbox>
              <div v-if="isFieldOverridden('button', 'text_bg_pressed')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('button', 'text_bg_pressed')" :modes="['hex']" :show-alpha="true" size="small" @update:value="v => setFieldValue('button', 'text_bg_pressed', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.text_bg_pressed }}</div>
            </div>

            <n-divider style="margin: 12px 0;" />

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'warning_color')" @update:checked="v => toggleFieldOverride('button', 'warning_color', v)">警告按钮颜色</n-checkbox>
              <div v-if="isFieldOverridden('button', 'warning_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('button', 'warning_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('button', 'warning_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.warning_color }}</div>
            </div>

            <div class="instance-field">
              <n-checkbox :checked="isFieldOverridden('button', 'danger_color')" @update:checked="v => toggleFieldOverride('button', 'danger_color', v)">危险按钮颜色</n-checkbox>
              <div v-if="isFieldOverridden('button', 'danger_color')" class="instance-field__control">
                <n-color-picker :value="getFieldValue('button', 'danger_color')" :modes="['hex']" :show-alpha="false" size="small" @update:value="v => setFieldValue('button', 'danger_color', v)" />
              </div>
              <div v-else class="instance-field__hint">继承全局: {{ form.button.danger_color }}</div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </template>

    <n-empty v-else :description="`请选择一个${itemTypeText}开始自定义`" style="padding: 40px 0;" />
  </n-card>
</template>

<style scoped>
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

.instance-section .instance-meta {
  padding: 12px 16px;
  background: var(--bg-surface);
  border-radius: 8px;
  border-left: 3px solid var(--n-primary-color);
  margin-top: 8px;
}
.instance-meta__page {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  color: var(--n-primary-color);
  background: color-mix(in srgb, var(--n-primary-color) 12%, transparent);
  padding: 2px 8px;
  border-radius: 10px;
  margin-bottom: 6px;
}
.instance-meta__title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.instance-meta__desc { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
.instance-meta__key { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.instance-meta__key code {
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  color: var(--n-primary-color);
}

.instance-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 8px;
}
.instance-field {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 16px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed var(--border-light);
}
.instance-field:last-child { border-bottom: none; }
.instance-field__control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.instance-field__control .n-slider { flex: 1; }
.instance-field__hint {
  font-size: 12px;
  color: var(--text-muted);
  font-style: italic;
  padding-left: 4px;
}
</style>
