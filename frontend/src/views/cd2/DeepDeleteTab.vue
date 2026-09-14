<script setup lang="ts">
/**
 * DeepDeleteTab — 神医深度删除 → CD2 联动删除配置
 *
 * 功能:
 * 1. 开启/关闭联动删除开关
 * 2. 自定义路径映射规则（支持本地挂载路径、HTTP 直链路径等任意前缀）
 * 3. 删除偏好（仅删文件 / 尝试删文件夹 / 自动判断）
 */
import { ref, reactive, onMounted } from 'vue'
import { cd2Api } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'DeepDeleteTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const saving = ref(false)

const config = reactive({
  enabled: false,
  delete_preference: 'files' as 'files' | 'folder' | 'auto',
  permanent_delete: false,
  notify_on_delete: true,
  path_mappings: [] as Array<{ from: string; to: string }>,
})

const preferenceOptions = [
  { title: '仅删文件', value: 'files', description: '删除 Mount Paths 中列出的具体文件，不删文件夹' },
  { title: '尝试删文件夹', value: 'folder', description: '用 Item Path 推导文件夹路径，删除整个文件夹（含内部所有文件）' },
  { title: '自动判断', value: 'auto', description: 'IsFolder=true 且 Type 为 Series/Season 时删文件夹，否则删文件' },
]

const loadConfig = async () => {
  loading.value = true
  try {
    const data = await cd2Api.getDeepDeleteConfig()
    config.enabled = data.enabled ?? false
    config.delete_preference = data.delete_preference ?? 'files'
    config.permanent_delete = data.permanent_delete ?? false
    config.notify_on_delete = data.notify_on_delete ?? true
    config.path_mappings = data.path_mappings ?? []
  } catch (e: any) {
    showError(e?.message || '获取配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  // 校验路径映射规则
  for (const rule of config.path_mappings) {
    if (!rule.from.trim()) {
      showError('映射规则的「匹配前缀」不能为空')
      return
    }
  }
  saving.value = true
  try {
    await cd2Api.saveDeepDeleteConfig({
      enabled: config.enabled,
      delete_preference: config.delete_preference,
      permanent_delete: config.permanent_delete,
      notify_on_delete: config.notify_on_delete,
      path_mappings: config.path_mappings,
    })
    success('配置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const addMapping = () => {
  config.path_mappings.push({ from: '', to: '' })
}

const removeMapping = (index: number) => {
  config.path_mappings.splice(index, 1)
}

const handleToggleEnabled = async (val: boolean | null) => {
  if (val === null) return
  if (val) {
    // 开启时不需要确认，直接设置
    config.enabled = true
  } else {
    config.enabled = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div>
    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" size="32" />
    </div>

    <template v-else>
      <!-- 功能说明 -->
      <v-card class="glass-card mb-4">
        <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-delete-variant</v-icon>
          <span class="text-subtitle-1 font-weight-bold">神医深度删除 → CD2 联动</span>
          <v-spacer />
          <v-switch
            v-model="config.enabled"
            color="primary"
            hide-details
            density="compact"
            @update:model-value="handleToggleEnabled"
          />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert type="info" variant="tonal" density="compact" class="mb-2">
            当神医执行「深度删除」时，自动通过 CD2 API 删除云盘上对应的文件/文件夹。<br />
            需要配置<strong>路径映射规则</strong>，将 Emby 发来的路径转换为 CD2 内部路径。
          </v-alert>
          <v-alert
            :type="config.permanent_delete ? 'error' : 'warning'"
            variant="tonal"
            density="compact"
          >
            {{ config.permanent_delete
              ? '当前为永久删除模式，文件将被直接删除，无法从回收站恢复！请谨慎使用。'
              : '当前为回收站模式，文件将移入回收站，可在 CD2 管理界面恢复。'
            }}
          </v-alert>
        </v-card-text>
      </v-card>

      <!-- 删除偏好 -->
      <v-card class="glass-card mb-4">
        <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-tune-variant</v-icon>
          <span class="text-subtitle-1 font-weight-bold">删除偏好</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-radio-group v-model="config.delete_preference" density="compact" hide-details>
            <v-radio
              v-for="opt in preferenceOptions"
              :key="opt.value"
              :value="opt.value"
              density="compact"
              hide-details
              class="mb-1"
            >
              <template #label>
                <div class="d-flex flex-column">
                  <span class="text-body-2 font-weight-medium">{{ opt.title }}</span>
                  <span class="text-caption text-medium-emphasis">{{ opt.description }}</span>
                </div>
              </template>
            </v-radio>
          </v-radio-group>
        </v-card-text>
      </v-card>

      <!-- 删除方式与通知 -->
      <v-card class="glass-card mb-4">
        <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-bell-cog-outline</v-icon>
          <span class="text-subtitle-1 font-weight-bold">删除方式与通知</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <!-- 永久删除开关 -->
          <div class="switch-row-lg mb-2">
            <v-switch
              v-model="config.permanent_delete"
              density="compact"
              hide-details
              color="error"
            />
            <div>
              <div class="switch-label">永久删除（不进回收站）</div>
              <div class="switch-desc">
                开启后直接永久删除文件，无法从回收站恢复。仅部分云盘支持（如阿里云盘）。
                关闭则删除到回收站，可在 CD2 管理界面恢复。
              </div>
            </div>
          </div>

          <v-divider class="mb-2" />

          <!-- TG 通知开关 -->
          <div class="switch-row-lg">
            <v-switch
              v-model="config.notify_on_delete"
              density="compact"
              hide-details
              color="primary"
            />
            <div>
              <div class="switch-label">发送 Telegram 通知</div>
              <div class="switch-desc">
                联动删除完成后发送 Telegram 通知，包含作品名称、删除模式、删除数量和路径列表。
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- 路径映射规则 -->
      <v-card class="glass-card mb-4">
        <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-swap-horizontal</v-icon>
          <span class="text-subtitle-1 font-weight-bold">路径映射规则</span>
          <v-chip size="x-small" variant="tonal" class="ml-2">{{ config.path_mappings.length }} 条</v-chip>
          <v-spacer />
          <v-btn
            color="primary"
            variant="tonal"
            size="small"
            prepend-icon="mdi-plus"
            @click="addMapping"
          >
            添加规则
          </v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert type="info" variant="tonal" density="compact" class="mb-3">
            <strong>匹配前缀</strong>：Emby 发来的路径开头部分（如本地挂载路径、HTTP 直链前缀等）<br />
            <strong>替换为</strong>：CD2 内部路径前缀（通常留空表示去掉前缀即可）<br />
            系统会按顺序匹配，找到第一个匹配的规则后进行替换。
          </v-alert>

          <div v-if="config.path_mappings.length === 0" class="text-center pa-6 text-medium-emphasis">
            暂无路径映射规则，点击右上角添加
          </div>

          <div v-else class="d-flex flex-column gap-3">
            <div
              v-for="(rule, index) in config.path_mappings"
              :key="index"
              class="mapping-row"
            >
              <div class="mapping-row__index">{{ index + 1 }}</div>
              <div class="mapping-row__fields">
                <v-text-field
                  v-model="rule.from"
                  label="匹配前缀 (Emby 路径开头)"
                  variant="outlined"
                  density="compact"
                  hide-details
                  placeholder="例如: /medata/CloudDrive"
                  class="mapping-row__from"
                />
                <v-icon class="mapping-row__arrow">mdi-arrow-right</v-icon>
                <v-text-field
                  v-model="rule.to"
                  label="替换为 (CD2 路径前缀，留空去掉前缀)"
                  variant="outlined"
                  density="compact"
                  hide-details
                  placeholder="留空 = 直接去掉前缀"
                  class="mapping-row__to"
                />
              </div>
              <v-btn
                icon="mdi-delete-outline"
                size="small"
                variant="text"
                color="error"
                @click="removeMapping(index)"
              />
            </div>
          </div>

          <!-- 示例 -->
          <v-expansion-panels variant="accordion" class="mt-4">
            <v-expansion-panel>
              <template #title>
                <div class="d-flex align-center ga-2">
                  <v-icon size="16">mdi-lightbulb-outline</v-icon>
                  <span class="text-body-2">查看配置示例</span>
                </div>
              </template>
              <template #text>
                <div class="text-body-2 text-medium-emphasis">
                  <p class="mb-2"><strong>示例 1 — 本地挂载路径：</strong></p>
                  <p class="ml-4 mb-3">
                    Emby 路径: <code>/medata/CloudDrive/123云盘/新番连载/PT/xxx.mkv</code><br />
                    匹配前缀: <code>/medata/CloudDrive</code><br />
                    替换为: <code>(留空)</code><br />
                    CD2 路径: <code>/123云盘/新番连载/PT/xxx.mkv</code>
                  </p>
                  <p class="mb-2"><strong>示例 2 — HTTP 直链路径：</strong></p>
                  <p class="ml-4 mb-3">
                    Emby 路径: <code>http://192.168.50.12:19798/static/http/192.168.50.12:19798/False//123云盘/xxx.mkv</code><br />
                    匹配前缀: <code>http://192.168.50.12:19798/static/http/192.168.50.12:19798/False</code><br />
                    替换为: <code>(留空)</code><br />
                    CD2 路径: <code>/123云盘/xxx.mkv</code>
                  </p>
                  <p class="mb-2"><strong>示例 3 — 自定义前缀替换：</strong></p>
                  <p class="ml-4">
                    Emby 路径: <code>/mnt/cloud/123云盘/xxx.mkv</code><br />
                    匹配前缀: <code>/mnt/cloud</code><br />
                    替换为: <code>/cloud_data</code><br />
                    CD2 路径: <code>/cloud_data/123云盘/xxx.mkv</code>
                  </p>
                </div>
              </template>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
      </v-card>

      <!-- 保存按钮 -->
      <div class="d-flex justify-end ga-2 mb-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="loadConfig"
        >
          重新加载
        </v-btn>
        <v-btn
          color="primary"
          prepend-icon="mdi-content-save"
          :loading="saving"
          @click="saveConfig"
        >
          保存配置
        </v-btn>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mapping-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.15);
}

.mapping-row__index {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.15);
  color: rgb(var(--v-theme-primary));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.mapping-row__fields {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  flex-wrap: wrap;
}

.mapping-row__from {
  flex: 1 1 40%;
  min-width: 200px;
}

.mapping-row__arrow {
  flex-shrink: 0;
  color: rgba(var(--v-theme-primary), 0.6);
}

.mapping-row__to {
  flex: 1 1 40%;
  min-width: 200px;
}
</style>
