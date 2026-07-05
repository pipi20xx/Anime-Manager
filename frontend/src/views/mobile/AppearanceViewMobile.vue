<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import {
  NCard, NSlider, NColorPicker, NButton, NSpace, NUpload, NImage,
  NSpin, NSelect, useMessage, NDivider, NPopconfirm, NTag, NCollapse,
  NCollapseItem, NSwitch
} from 'naive-ui'
import type { UploadFileInfo } from 'naive-ui'
import {
  appearanceApi,
  type AppearanceConfig,
  type AppearanceImage
} from '../../api/appearance'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { useAppearanceConfigIO } from '../../composables/useAppearanceConfigIO'
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

const form = reactive<AppearanceConfig>({
  global: { ...appearanceConfig.value.global },
  modal: { ...appearanceConfig.value.modal },
  card: { ...appearanceConfig.value.card },
  tabs: { ...appearanceConfig.value.tabs },
  input: { ...appearanceConfig.value.input },
  search: { ...appearanceConfig.value.search },
  list: { ...appearanceConfig.value.list },
  // mobile 端暂不提供实例级自定义 UI，但保留 instances 字段以免保存时擦除
  instances: JSON.parse(JSON.stringify(appearanceConfig.value.instances || {})),
})

const imageOptions = computed(() => {
  const opts: { label: string; value: string }[] = [{ label: '无背景图', value: '' }]
  for (const img of images.value) {
    opts.push({ label: img.filename.slice(0, 16), value: img.filename })
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

// ============= 配置导入/导出 =============
const {
  fileInput,
  importLoading,
  exportLoading,
  exportConfig,
  triggerImport,
  handleFileImport
} = useAppearanceConfigIO()

const handleExportConfig = () => { exportConfig(form) }
const onImportFileChange = (e: Event) => { handleFileImport(e, form, preview) }

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
    Object.assign(form.list, appearanceConfig.value.list)
    form.instances = JSON.parse(JSON.stringify(appearanceConfig.value.instances || {}))
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
  <div class="m-appearance-view">
    <div class="m-page-header">
      <div>
        <h1>外观设置</h1>
        <div class="m-subtitle">自定义界面外观与视觉效果</div>
      </div>
      <n-space>
        <n-button v-bind="getButtonStyle('primary')" size="small" :loading="exportLoading" @click="handleExportConfig">导出</n-button>
        <n-button v-bind="getButtonStyle('primary')" size="small" :loading="importLoading" @click="triggerImport">导入</n-button>
        <n-popconfirm @positive-click="handleReset">
          <template #trigger>
            <n-button v-bind="getButtonStyle('warning')" size="small">恢复默认</n-button>
          </template>
          确定恢复默认？
        </n-popconfirm>
        <n-button type="primary" size="small" :loading="saving" @click="handleSave">保存</n-button>
      </n-space>
    </div>

    <n-spin :show="loading">
      <n-collapse :default-expanded-names="['global', 'modal', 'images']">
        <!-- 全局背景 -->
        <n-collapse-item name="global">
          <template #header>
            <div class="m-collapse-header">
              <span>全局背景</span>
              <n-switch v-model:value="form.global.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.global.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景图片</div>
              <n-select v-model:value="form.global.background_image" :options="imageOptions" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">遮罩暗化 {{ (form.global.background_overlay_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.global.background_overlay_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">背景模糊 {{ form.global.background_blur }}px</div>
              <n-slider v-model:value="form.global.background_blur" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">布局不透明度 {{ (form.global.layout_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.global.layout_opacity" :min="0.1" :max="1" :step="0.05" @update:value="preview" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 弹框外观 -->
        <n-collapse-item name="modal">
          <template #header>
            <div class="m-collapse-header">
              <span>弹框外观</span>
              <n-switch v-model:value="form.modal.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.modal.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景图片</div>
              <n-select v-model:value="form.modal.background_image" :options="imageOptions" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">背景模糊 {{ form.modal.background_blur }}px</div>
              <n-slider v-model:value="form.modal.background_blur" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">背景不透明度 {{ (form.modal.background_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.modal.background_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row" v-if="form.modal.background_image">
              <div class="m-form-label">遮罩暗化 {{ (form.modal.background_overlay_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.modal.background_overlay_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">边框颜色</div>
              <n-color-picker v-model:value="form.modal.border_color" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">边框宽度 {{ form.modal.border_width }}px</div>
              <n-slider v-model:value="form.modal.border_width" :min="0" :max="5" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">圆角 {{ form.modal.border_radius }}px</div>
              <n-slider v-model:value="form.modal.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 卡片外观 -->
        <n-collapse-item name="card">
          <template #header>
            <div class="m-collapse-header">
              <span>卡片外观</span>
              <n-switch v-model:value="form.card.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.card.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景图片</div>
              <n-select v-model:value="form.card.background_image" :options="imageOptions" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">背景不透明度 {{ (form.card.background_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.card.background_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row" v-if="form.card.background_image">
              <div class="m-form-label">遮罩暗化 {{ (form.card.background_overlay_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.card.background_overlay_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">圆角 {{ form.card.border_radius }}px</div>
              <n-slider v-model:value="form.card.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">背景模糊 {{ form.card.blur }}px</div>
              <n-slider v-model:value="form.card.blur" :min="0" :max="20" :step="1" @update:value="preview" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 标签页外观 -->
        <n-collapse-item name="tabs">
          <template #header>
            <div class="m-collapse-header">
              <span>标签页外观</span>
              <n-switch v-model:value="form.tabs.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.tabs.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景模糊 {{ form.tabs.nav_blur }}px</div>
              <n-slider v-model:value="form.tabs.nav_blur" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">导航栏不透明度 {{ (form.tabs.nav_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.tabs.nav_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">激活标签背景色</div>
              <n-color-picker v-model:value="form.tabs.tab_active_bg" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">激活标签文字色</div>
              <n-color-picker v-model:value="form.tabs.tab_active_text_color" :modes="['hex']" :show-alpha="false" @update:value="preview" size="small" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 输入框外观 -->
        <n-collapse-item name="input">
          <template #header>
            <div class="m-collapse-header">
              <span>输入框外观（文本框/下拉框/时间）</span>
              <n-switch v-model:value="form.input.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.input.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景不透明度 {{ (form.input.bg_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.input.bg_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">圆角 {{ form.input.border_radius }}px</div>
              <n-slider v-model:value="form.input.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">高度 {{ form.input.height }}px</div>
              <n-slider v-model:value="form.input.height" :min="36" :max="72" :step="2" @update:value="preview" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 搜索框外观 -->
        <n-collapse-item name="search">
          <template #header>
            <div class="m-collapse-header">
              <span>搜索框外观</span>
              <n-switch v-model:value="form.search.enabled" @update:value="preview" size="small" @click.stop />
            </div>
          </template>
          <template v-if="form.search.enabled">
            <div class="m-form-row">
              <div class="m-form-label">背景不透明度 {{ (form.search.bg_opacity * 100).toFixed(0) }}%</div>
              <n-slider v-model:value="form.search.bg_opacity" :min="0" :max="1" :step="0.05" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">圆角 {{ form.search.border_radius }}px</div>
              <n-slider v-model:value="form.search.border_radius" :min="0" :max="30" :step="1" @update:value="preview" />
            </div>
            <div class="m-form-row">
              <div class="m-form-label">高度 {{ form.search.height }}px</div>
              <n-slider v-model:value="form.search.height" :min="32" :max="60" :step="2" @update:value="preview" />
            </div>
          </template>
        </n-collapse-item>

        <!-- 图片管理 -->
        <n-collapse-item title="背景图片管理" name="images">
          <n-upload :max="1" accept="image/*" :show-file-list="false" @change="handleUpload">
            <n-button type="primary" ghost size="small">上传图片</n-button>
          </n-upload>
          <div v-if="images.length > 0" class="m-image-grid">
            <div v-for="img in images" :key="img.filename" class="m-image-item">
              <n-image :src="`/api/appearance/image/${img.filename}`" object-fit="cover" width="80" height="60" :preview-disabled="false" style="border-radius: 6px;" />
              <div class="m-image-info">
                <span>{{ formatFileSize(img.size) }}</span>
                <n-popconfirm @positive-click="handleDeleteImage(img.filename)">
                  <template #trigger>
                    <n-button size="tiny" type="error" ghost>删除</n-button>
                  </template>
                  确定删除？
                </n-popconfirm>
              </div>
            </div>
          </div>
          <div v-else class="m-empty-images">暂无图片，请上传</div>
        </n-collapse-item>
      </n-collapse>
    </n-spin>

    <!-- 导入配置文件选择（隐藏） -->
    <input
      type="file"
      ref="fileInput"
      accept=".zip"
      style="display: none"
      @change="onImportFileChange"
    />
  </div>
</template>

<style scoped>
.m-appearance-view { width: 100%; padding-bottom: calc(60px + env(safe-area-inset-bottom)); }

.m-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.m-page-header h1 { margin: 0; font-size: 20px; color: var(--text-primary); }
.m-subtitle { font-size: 10px; color: var(--n-primary-color); letter-spacing: 1px; font-weight: bold; margin-top: 2px; }

.m-collapse-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-form-row { margin-bottom: 12px; }
.m-form-row:last-child { margin-bottom: 0; }
.m-form-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }

.m-image-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.m-image-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.m-image-info { display: flex; align-items: center; gap: 8px; font-size: 10px; color: var(--text-muted); }

.m-empty-images { padding: 30px 0; text-align: center; color: var(--text-muted); font-size: 12px; }
</style>
