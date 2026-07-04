<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import {
  NCard, NSlider, NColorPicker, NButton, NSpace, NUpload, NImage,
  NSpin, NSelect, useMessage, NDivider, NPopconfirm, NTag, NSwitch
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import {
  appearanceApi,
  type AppearanceConfig,
  type AppearanceImage
} from '../../api/appearance'
import {
  appearanceConfig,
  saveAppearanceConfig,
  resetAppearanceConfig,
  applyAppearanceToCss
} from '../../store/appearanceStore'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const images = ref<AppearanceImage[]>([])

// 本地编辑副本
const form = reactive<AppearanceConfig>({
  global: { ...appearanceConfig.value.global },
  modal: { ...appearanceConfig.value.modal },
  card: { ...appearanceConfig.value.card },
  tabs: { ...appearanceConfig.value.tabs },
  input: { ...appearanceConfig.value.input },
  search: { ...appearanceConfig.value.search },
  list: { ...appearanceConfig.value.list },
})

// 图片选项（修复：返回 .value）
const imageOptions = computed(() => {
  const opts: { label: string; value: string }[] = [{ label: '无背景图', value: '' }]
  for (const img of images.value) {
    opts.push({ label: img.filename.slice(0, 20), value: img.filename })
  }
  return opts
})

onMounted(async () => {
  loading.value = true
  try {
    const res = await appearanceApi.listImages()
    images.value = res.data || []
  } catch (e) {
    console.warn('加载图片列表失败', e)
  } finally {
    loading.value = false
  }
})

const preview = () => { applyAppearanceToCss(form) }

const handleSave = async () => {
  saving.value = true
  try {
    await saveAppearanceConfig(form)
    message.success('外观设置已保存')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleReset = async () => {
  try {
    await resetAppearanceConfig()
    Object.assign(form.global, appearanceConfig.value.global)
    Object.assign(form.modal, appearanceConfig.value.modal)
    Object.assign(form.card, appearanceConfig.value.card)
    Object.assign(form.tabs, appearanceConfig.value.tabs)
    Object.assign(form.input, appearanceConfig.value.input)
    Object.assign(form.search, appearanceConfig.value.search)
    message.success('已恢复默认设置')
  } catch (e: any) {
    message.error('重置失败')
  }
}

const handleUpload = async ({ file }: { file: UploadFileInfo }) => {
  if (!file.file) return
  try {
    const res = await appearanceApi.uploadImage(file.file)
    images.value.push({ filename: res.data.filename, size: file.file.size })
    message.success('图片上传成功')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '上传失败')
  }
}

const handleDeleteImage = async (filename: string) => {
  try {
    await appearanceApi.deleteImage(filename)
    images.value = images.value.filter(i => i.filename !== filename)
    if (form.global.background_image === filename) form.global.background_image = ''
    if (form.modal.background_image === filename) form.modal.background_image = ''
    if (form.card.background_image === filename) form.card.background_image = ''
    preview()
    message.success('图片已删除')
  } catch (e: any) {
    message.error('删除失败')
  }
}

const formatFileSize = (size: number) => {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="appearance-view">
    <div class="page-header">
      <div>
        <h1>外观设置</h1>
        <div class="subtitle">自定义界面外观与视觉效果</div>
      </div>
      <n-space>
        <n-popconfirm @positive-click="handleReset">
          <template #trigger>
            <n-button type="warning" ghost>恢复默认</n-button>
          </template>
          确定要恢复所有外观设置为默认值吗？
        </n-popconfirm>
        <n-button type="primary" :loading="saving" @click="handleSave">保存设置</n-button>
      </n-space>
    </div>

    <n-spin :show="loading">
      <div class="settings-grid">
        <!-- ===== 全局背景 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">全局背景</div>
              <div class="section-desc">设置页面全局背景图片与遮罩效果</div>
            </div>
            <n-switch v-model:value="form.global.enabled" @update:value="preview" />
          </div>
          <template v-if="form.global.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景图片</div>
              <div class="form-control">
                <n-select v-model:value="form.global.background_image" :options="imageOptions" @update:value="preview" placeholder="选择背景图片" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">遮罩暗化 <n-tag size="small" type="info">{{ (form.global.background_overlay_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.global.background_overlay_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">背景模糊 <n-tag size="small" type="info">{{ form.global.background_blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.global.background_blur" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">布局不透明度 <n-tag size="small" type="info">{{ (form.global.layout_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.global.layout_opacity" :min="0.1" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 弹框外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">弹框外观</div>
              <div class="section-desc">设置表单弹框的背景、模糊、边框等视觉效果</div>
            </div>
            <n-switch v-model:value="form.modal.enabled" @update:value="preview" />
          </div>
          <template v-if="form.modal.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景图片</div>
              <div class="form-control">
                <n-select v-model:value="form.modal.background_image" :options="imageOptions" @update:value="preview" placeholder="选择背景图片" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">模糊程度 <n-tag size="small" type="info">{{ form.modal.background_blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.modal.background_blur" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">背景不透明度 <n-tag size="small" type="info">{{ (form.modal.background_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.modal.background_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">边框颜色</div>
              <div class="form-control">
                <n-color-picker v-model:value="form.modal.border_color" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">边框宽度 <n-tag size="small" type="info">{{ form.modal.border_width }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.modal.border_width" :min="0" :max="5" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">圆角 <n-tag size="small" type="info">{{ form.modal.border_radius }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.modal.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 卡片外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">卡片外观</div>
              <div class="section-desc">设置卡片、DataTable 表格容器的透明度与圆角</div>
            </div>
            <n-switch v-model:value="form.card.enabled" @update:value="preview" />
          </div>
          <template v-if="form.card.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景图片</div>
              <div class="form-control">
                <n-select v-model:value="form.card.background_image" :options="imageOptions" @update:value="preview" placeholder="选择背景图片" />
              </div>
            </div>
            <div class="form-row" v-if="form.card.background_image || form.global.enabled">
              <div class="form-label">背景不透明度 <n-tag size="small" type="info">{{ (form.card.background_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.card.background_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">圆角 <n-tag size="small" type="info">{{ form.card.border_radius }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.card.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 标签页外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">标签页外观</div>
              <div class="section-desc">设置 Tabs 组件的视觉效果</div>
            </div>
            <n-switch v-model:value="form.tabs.enabled" @update:value="preview" />
          </div>
          <template v-if="form.tabs.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">导航栏模糊 <n-tag size="small" type="info">{{ form.tabs.nav_blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.tabs.nav_blur" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">导航栏不透明度 <n-tag size="small" type="info">{{ (form.tabs.nav_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.tabs.nav_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">激活标签背景色</div>
              <div class="form-control">
                <n-color-picker v-model:value="form.tabs.tab_active_bg" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">激活标签文字色</div>
              <div class="form-control">
                <n-color-picker v-model:value="form.tabs.tab_active_text_color" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 输入框外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">输入框外观</div>
              <div class="section-desc">设置文本框 / 下拉框 / 时间选择器的视觉效果</div>
            </div>
            <n-switch v-model:value="form.input.enabled" @update:value="preview" />
          </div>
          <template v-if="form.input.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景不透明度 <n-tag size="small" type="info">{{ (form.input.bg_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.input.bg_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">圆角 <n-tag size="small" type="info">{{ form.input.border_radius }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.input.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">高度 <n-tag size="small" type="info">{{ form.input.height }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.input.height" :min="36" :max="72" :step="2" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">模糊 <n-tag size="small" type="info">{{ form.input.blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.input.blur" :min="0" :max="20" :step="1" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 搜索框外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">搜索框外观</div>
              <div class="section-desc">设置 AppSearchField 组件的视觉效果</div>
            </div>
            <n-switch v-model:value="form.search.enabled" @update:value="preview" />
          </div>
          <template v-if="form.search.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景不透明度 <n-tag size="small" type="info">{{ (form.search.bg_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.search.bg_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">圆角 <n-tag size="small" type="info">{{ form.search.border_radius }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.search.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">高度 <n-tag size="small" type="info">{{ form.search.height }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.search.height" :min="32" :max="60" :step="2" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">模糊 <n-tag size="small" type="info">{{ form.search.blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.search.blur" :min="0" :max="20" :step="1" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 列表外观 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true">
          <div class="section-header">
            <div>
              <div class="section-title">列表外观</div>
              <div class="section-desc">设置列表项、DataTable 表格行的透明度与圆角</div>
            </div>
            <n-switch v-model:value="form.list.enabled" @update:value="preview" />
          </div>
          <template v-if="form.list.enabled">
            <n-divider />
            <div class="form-row">
              <div class="form-label">背景不透明度 <n-tag size="small" type="info">{{ (form.list.bg_opacity * 100).toFixed(0) }}%</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.list.bg_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">圆角 <n-tag size="small" type="info">{{ form.list.border_radius }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.list.border_radius" :min="0" :max="20" :step="1" @update:value="preview" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-label">模糊 <n-tag size="small" type="info">{{ form.list.blur }}px</n-tag></div>
              <div class="form-control">
                <n-slider v-model:value="form.list.blur" :min="0" :max="20" :step="1" @update:value="preview" />
              </div>
            </div>
          </template>
        </n-card>

        <!-- ===== 图片管理 ===== -->
        <n-card class="app-card-config settings-section" :bordered="true" style="grid-column: 1 / -1;">
          <div class="section-title">背景图片管理</div>
          <div class="section-desc">上传、预览和删除背景图片</div>
          <n-divider />
          <n-upload :max="1" accept="image/*" :show-file-list="false" @change="handleUpload">
            <n-button type="primary" ghost>上传图片</n-button>
          </n-upload>
          <div v-if="images.length > 0" class="image-grid">
            <div v-for="img in images" :key="img.filename" class="image-item">
              <n-image :src="`/api/appearance/image/${img.filename}`" object-fit="cover" width="120" height="80" :preview-disabled="false" style="border-radius: 8px;" />
              <div class="image-info">
                <span class="image-name">{{ img.filename.slice(0, 12) }}...</span>
                <span class="image-size">{{ formatFileSize(img.size) }}</span>
              </div>
              <n-popconfirm @positive-click="handleDeleteImage(img.filename)">
                <template #trigger>
                  <n-button size="tiny" type="error" ghost>删除</n-button>
                </template>
                确定删除此图片？
              </n-popconfirm>
            </div>
          </div>
          <div v-else class="empty-images">暂无图片，请上传</div>
        </n-card>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.appearance-view { width: 100%; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h1 { margin: 0; font-size: 24px; color: var(--text-primary); }
.subtitle { font-size: 11px; color: var(--n-primary-color); letter-spacing: 2px; font-weight: bold; margin-top: 4px; }

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.settings-section { break-inside: avoid; }

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

.image-grid { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; }
.image-item { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 8px; border-radius: 8px; background: var(--bg-surface); border: 1px solid var(--border-light); }
.image-info { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.image-name { font-size: 11px; color: var(--text-secondary); }
.image-size { font-size: 10px; color: var(--text-muted); }

.empty-images { padding: 40px 0; text-align: center; color: var(--text-muted); font-size: 13px; }
</style>
