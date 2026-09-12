<script setup lang="ts">
/**
 * ProtoTab — CD2 协议文件管理
 * 展示 clouddrive.proto 版本信息，支持手动强制从官网更新并重新编译。
 */
import { onMounted, ref } from 'vue'
import { cd2Api } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'ProtoTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const loading = ref(false)
const updating = ref(false)
const info = ref<any>({})

const formatTime = (ts?: number) => {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

const loadInfo = async () => {
  loading.value = true
  try {
    info.value = await cd2Api.getProtoInfo()
  } catch (e: any) {
    showError(e?.message || '获取协议信息失败')
  } finally {
    loading.value = false
  }
}

const forceUpdate = async () => {
  const ok = await confirm(
    '将从 CD2 官网重新下载 clouddrive.proto 并重新编译加载，确认继续吗？'
  )
  if (!ok) return
  updating.value = true
  try {
    const res = await cd2Api.forceUpdateProto()
    if (res?.success) {
      success(res.message || '协议已更新')
    } else {
      showError(res?.message || '更新失败')
    }
    await loadInfo()
  } catch (e: any) {
    showError(e?.message || '更新失败')
  } finally {
    updating.value = false
  }
}

onMounted(loadInfo)
</script>

<template>
  <v-card class="glass-card mb-4">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-file-code-outline</v-icon>
      CD2 gRPC 协议 (clouddrive.proto)
      <v-spacer />
      <v-btn
        color="primary"
        variant="tonal"
        size="small"
        prepend-icon="mdi-cloud-download-outline"
        :loading="updating"
        @click="forceUpdate"
      >
        强制更新协议
      </v-btn>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <div v-if="loading && !info.gen_dir" class="d-flex justify-center pa-6">
        <v-progress-circular indeterminate color="primary" />
      </div>
      <template v-else>
        <v-row>
          <v-col cols="12" sm="6">
            <div class="text-caption text-medium-emphasis mb-1">协议版本 (MD5)</div>
            <v-chip size="small" variant="tonal" color="primary">
              {{ info.hash ? info.hash.slice(0, 8) : '未知' }}
            </v-chip>
            <span class="text-caption text-medium-emphasis ml-2">{{ info.hash || '-' }}</span>
          </v-col>
          <v-col cols="12" sm="6">
            <div class="text-caption text-medium-emphasis mb-1">最近更新时间</div>
            <div class="text-body-2">{{ formatTime(info.updated_at) }}</div>
          </v-col>
          <v-col cols="12" sm="6">
            <div class="text-caption text-medium-emphasis mb-1">编译产物 (pb2 / pb2_grpc)</div>
            <div class="d-flex gap-2">
              <v-chip size="x-small" variant="tonal" :color="info.pb2_exists ? 'success' : 'error'">
                clouddrive_pb2.py
              </v-chip>
              <v-chip size="x-small" variant="tonal" :color="info.pb2_grpc_exists ? 'success' : 'error'">
                clouddrive_pb2_grpc.py
              </v-chip>
            </div>
          </v-col>
          <v-col cols="12" sm="6">
            <div class="text-caption text-medium-emphasis mb-1">运行时模块状态</div>
            <v-chip size="small" variant="tonal" :color="info.loaded ? 'success' : 'grey'">
              {{ info.loaded ? '已加载' : '未加载' }}
            </v-chip>
          </v-col>
          <v-col cols="12">
            <div class="text-caption text-medium-emphasis mb-1">存储目录</div>
            <div class="text-body-2 text-truncate">{{ info.gen_dir || '-' }}</div>
          </v-col>
        </v-row>

        <v-alert type="info" variant="tonal" density="compact" class="mt-2">
          系统启动时会自动比对官网协议版本并按需更新；此按钮用于手动强制重新下载与编译（如协议刚更新但服务未重启）。
        </v-alert>
      </template>
    </v-card-text>
  </v-card>
</template>
