<script setup lang="ts">
/**
 * AppearanceView — 外观设置
 *
 * 功能:
 * - 全局背景设置
 * - 弹框/卡片/标签页/输入框外观
 * - 背景图片管理
 * - 配置导入/导出/重置
 * - 实时预览
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { appearanceApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'AppearanceView' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const saving = ref(false)
const activeTab = ref('global')

interface AppearanceImage {
  filename: string
  size: number
}

const images = ref<AppearanceImage[]>([])

// 表单数据
const form = reactive({
  global: {
    enabled: false,
    background_image: '',
    background_overlay_opacity: 0.5,
    background_blur: 0,
    layout_opacity: 0.95,
  },
  modal: {
    enabled: false,
    background_image: '',
    background_blur: 0,
    background_opacity: 0.85,
    background_overlay_opacity: 0.5,
    border_color: '#ffffff',
    border_width: 1,
    border_radius: 16,
  },
  card: {
    enabled: false,
    background_image: '',
    background_opacity: 0.85,
    background_overlay_opacity: 0.5,
    border_radius: 16,
    blur: 0,
  },
  tabs: {
    enabled: false,
    nav_blur: 0,
    nav_opacity: 0.85,
    tab_active_bg: '#18a058',
    tab_active_text_color: '#ffffff',
    tab_height: 40,
    tab_gap: 4,
    tab_padding: 12,
    tab_border_radius: 8,
    tab_font_size: 14,
  },
  input: {
    enabled: false,
    bg_opacity: 0.85,
    border_radius: 8,
    height: 34,
    blur: 0,
  },
})

// 图片选项
const imageOptions = computed(() => {
  const opts: { title: string; value: string }[] = [{ title: '无背景图', value: '' }]
  for (const img of images.value) {
    opts.push({ title: img.filename.slice(0, 20), value: img.filename })
  }
  return opts
})

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const [configData, imagesData] = await Promise.allSettled([
      appearanceApi.getConfig(),
      appearanceApi.getImages(),
    ])
    if (configData.status === 'fulfilled' && configData.value) {
      const config = configData.value
      if (config.global) Object.assign(form.global, config.global)
      if (config.modal) Object.assign(form.modal, config.modal)
      if (config.card) Object.assign(form.card, config.card)
      if (config.tabs) Object.assign(form.tabs, config.tabs)
      if (config.input) Object.assign(form.input, config.input)
    }
    if (imagesData.status === 'fulfilled') {
      images.value = imagesData.value?.data || imagesData.value || []
    }
  } catch (e) {
    showError('加载外观配置失败')
  } finally {
    loading.value = false
  }
}

// 保存配置
async function handleSave() {
  saving.value = true
  try {
    await appearanceApi.updateConfig({ ...form })
    success('外观设置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// 重置配置
async function handleReset() {
  const ok = await confirm('确定要恢复所有外观设置为默认值吗？')
  if (!ok) return
  try {
    await appearanceApi.updateConfig({
      global: { enabled: false, background_image: '', background_overlay_opacity: 0.5, background_blur: 0, layout_opacity: 0.95 },
      modal: { enabled: false, background_image: '', background_blur: 0, background_opacity: 0.85, background_overlay_opacity: 0.5, border_color: '#ffffff', border_width: 1, border_radius: 16 },
      card: { enabled: false, background_image: '', background_opacity: 0.85, background_overlay_opacity: 0.5, border_radius: 16, blur: 0 },
      tabs: { enabled: false, nav_blur: 0, nav_opacity: 0.85, tab_active_bg: '#18a058', tab_active_text_color: '#ffffff', tab_height: 40, tab_gap: 4, tab_padding: 12, tab_border_radius: 8, tab_font_size: 14 },
      input: { enabled: false, bg_opacity: 0.85, border_radius: 8, height: 34, blur: 0 },
    })
    await loadConfig()
    success('已恢复默认设置')
  } catch (e) {
    showError('重置失败')
  }
}

// 上传图片
async function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await appearanceApi.uploadImage(formData)
    images.value.push({ filename: res?.data?.filename || res?.filename || file.name, size: file.size })
    success('图片上传成功')
  } catch (e: any) {
    showError(e?.message || '上传失败')
  }
  input.value = ''
}

// 删除图片
async function handleDeleteImage(filename: string) {
  const ok = await confirm('确定删除图片「' + filename + '」吗？')
  if (!ok) return
  try {
    await appearanceApi.deleteImage(filename)
    images.value = images.value.filter(i => i.filename !== filename)
    if (form.global.background_image === filename) form.global.background_image = ''
    if (form.modal.background_image === filename) form.modal.background_image = ''
    if (form.card.background_image === filename) form.card.background_image = ''
    success('图片已删除')
  } catch (e) {
    showError('删除失败')
  }
}

function formatFileSize(size: number): string {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6 d-flex align-center justify-space-between flex-wrap ga-3">
      <div>
        <h1 class="text-h5 font-weight-bold">外观设置</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">自定义界面外观与视觉效果</div>
      </div>
      <div class="d-flex ga-2">
        <v-btn variant="tonal" color="warning" @click="handleReset">恢复默认</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" @click="handleSave">保存设置</v-btn>
      </div>
    </div>

    <v-tabs v-model="activeTab" color="primary" class="mb-4">
      <v-tab value="global">全局设置</v-tab>
      <v-tab value="components">组件外观</v-tab>
      <v-tab value="images">图片管理</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- 全局设置 -->
      <v-window-item value="global">
        <v-row>
          <!-- 全局背景 -->
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">全局背景</div>
                  <div class="text-caption text-medium-emphasis">设置页面全局背景图片与遮罩效果</div>
                </div>
                <v-switch v-model="form.global.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text v-if="form.global.enabled" class="pa-4">
                <v-select v-model="form.global.background_image" label="背景图片" :items="imageOptions" density="compact" class="mb-3" />
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">遮罩暗化</span>
                  <v-slider v-model="form.global.background_overlay_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.global.background_overlay_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景模糊</span>
                  <v-slider v-model="form.global.background_blur" :min="0" :max="30" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.global.background_blur }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">布局不透明度</span>
                  <v-slider v-model="form.global.layout_opacity" :min="0.1" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.global.layout_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 弹框外观 -->
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">弹框外观</div>
                  <div class="text-caption text-medium-emphasis">设置表单弹框的背景、边框等视觉效果</div>
                </div>
                <v-switch v-model="form.modal.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text v-if="form.modal.enabled" class="pa-4">
                <v-select v-model="form.modal.background_image" label="背景图片" :items="imageOptions" density="compact" class="mb-3" />
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景模糊</span>
                  <v-slider v-model="form.modal.background_blur" :min="0" :max="30" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.modal.background_blur }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景不透明度</span>
                  <v-slider v-model="form.modal.background_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.modal.background_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div v-if="form.modal.background_image" class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">遮罩暗化</span>
                  <v-slider v-model="form.modal.background_overlay_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.modal.background_overlay_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">边框宽度</span>
                  <v-slider v-model="form.modal.border_width" :min="0" :max="5" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.modal.border_width }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">圆角</span>
                  <v-slider v-model="form.modal.border_radius" :min="0" :max="30" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.modal.border_radius }}px</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- 组件外观 -->
      <v-window-item value="components">
        <v-row>
          <!-- 卡片外观 -->
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">卡片外观</div>
                  <div class="text-caption text-medium-emphasis">设置卡片的透明度与圆角</div>
                </div>
                <v-switch v-model="form.card.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text v-if="form.card.enabled" class="pa-4">
                <v-select v-model="form.card.background_image" label="背景图片" :items="imageOptions" density="compact" class="mb-3" />
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景不透明度</span>
                  <v-slider v-model="form.card.background_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.card.background_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div v-if="form.card.background_image" class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">遮罩暗化</span>
                  <v-slider v-model="form.card.background_overlay_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.card.background_overlay_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">圆角</span>
                  <v-slider v-model="form.card.border_radius" :min="0" :max="30" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.card.border_radius }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景模糊</span>
                  <v-slider v-model="form.card.blur" :min="0" :max="20" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.card.blur }}px</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 标签页外观 -->
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">标签页外观</div>
                  <div class="text-caption text-medium-emphasis">设置 Tabs 组件的视觉效果</div>
                </div>
                <v-switch v-model="form.tabs.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text v-if="form.tabs.enabled" class="pa-4">
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">导航栏不透明度</span>
                  <v-slider v-model="form.tabs.nav_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.tabs.nav_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">标签高度</span>
                  <v-slider v-model="form.tabs.tab_height" :min="28" :max="72" :step="2" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.tabs.tab_height }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">标签间距</span>
                  <v-slider v-model="form.tabs.tab_gap" :min="0" :max="24" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.tabs.tab_gap }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">标签圆角</span>
                  <v-slider v-model="form.tabs.tab_border_radius" :min="0" :max="24" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.tabs.tab_border_radius }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">文字大小</span>
                  <v-slider v-model="form.tabs.tab_font_size" :min="10" :max="20" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.tabs.tab_font_size }}px</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- 输入框外观 -->
          <v-col cols="12" md="6">
            <v-card class="glass-card">
              <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
                <div>
                  <div class="text-subtitle-1 font-weight-bold">输入框外观</div>
                  <div class="text-caption text-medium-emphasis">设置文本框 / 下拉框的视觉效果</div>
                </div>
                <v-switch v-model="form.input.enabled" density="compact" hide-details color="primary" />
              </v-card-title>
              <v-divider />
              <v-card-text v-if="form.input.enabled" class="pa-4">
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景不透明度</span>
                  <v-slider v-model="form.input.bg_opacity" :min="0" :max="1" :step="0.05" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ (form.input.bg_opacity * 100).toFixed(0) }}%</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">圆角</span>
                  <v-slider v-model="form.input.border_radius" :min="0" :max="30" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.input.border_radius }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3 mb-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">高度</span>
                  <v-slider v-model="form.input.height" :min="20" :max="72" :step="2" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.input.height }}px</v-chip>
                </div>
                <div class="d-flex align-center ga-3">
                  <span class="text-body-2 text-medium-emphasis label-min-w">背景模糊</span>
                  <v-slider v-model="form.input.blur" :min="0" :max="20" :step="1" hide-details thumb-label />
                  <v-chip size="small" variant="tonal">{{ form.input.blur }}px</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- 图片管理 -->
      <v-window-item value="images">
        <v-card class="glass-card">
          <v-card-title class="pa-4 d-flex align-center justify-space-between">
            <div>
              <div class="text-subtitle-1 font-weight-bold">背景图片管理</div>
              <div class="text-caption text-medium-emphasis">上传、预览和删除背景图片</div>
            </div>
            <v-btn color="primary" variant="tonal" prepend-icon="mdi-upload" @click="($refs.fileInput as any)?.click()">
              上传图片
            </v-btn>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              style="display: none"
              @change="handleImageUpload"
            />

            <v-row v-if="images.length > 0">
              <v-col v-for="img in images" :key="img.filename" cols="6" sm="6" md="3" lg="3">
                <v-card class="glass-card">
                  <v-img
                    :src="'/api/appearance/image/' + img.filename"
                    cover
                    aspect-ratio="16/9"
                    rounded="lg"
                    class="ma-2"
                  />
                  <v-card-text class="pa-2 pt-0">
                    <div class="text-caption text-truncate">{{ img.filename }}</div>
                    <div class="text-caption text-medium-emphasis">{{ formatFileSize(img.size) }}</div>
                  </v-card-text>
                  <v-card-actions class="pa-2 pt-0">
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="handleDeleteImage(img.filename)">删除</v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>

            <div v-else class="text-center pa-8">
              <v-icon size="48" color="primary" class="mb-3">mdi-image-outline</v-icon>
              <div class="text-body-1">暂无图片，请上传</div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>
