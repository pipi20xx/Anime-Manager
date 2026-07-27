/**
 * 系统全局 Store — 管理 WebSocket、登录状态、进度等
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ProgressData } from '@/types'

export const useSystemStore = defineStore('system', () => {
  // --- WebSocket 状态 ---
  const isConnected = ref(false)
  const scanProgress = ref<ProgressData>({ status: 'idle', current: 0, total: 0, message: '' })
  const downloadProgress = ref<ProgressData>({ status: 'idle', current: 0, total: 0, message: '' })
  const logs = ref<string[]>([])

  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setInterval> | null = null

  // --- 登录状态 ---
  const isLoggedIn = ref(!!(localStorage.getItem('apm_access_token') || localStorage.getItem('apm_external_token')))
  const username = ref(localStorage.getItem('apm_username') || '')

  // --- 日志终端 ---
  const showLogModal = ref(false)

  // --- 计算属性 ---
  const hasActiveProgress = computed(() => {
    const sp = scanProgress.value
    const dp = downloadProgress.value
    return (sp.status === 'running' || sp.status === 'scanning') ||
           (dp.status === 'running' || dp.status === 'scanning')
  })

  // --- WebSocket 方法 ---
  function connect() {
    if (socket) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws`

    socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      isConnected.value = true
      if (reconnectTimer) {
        clearInterval(reconnectTimer)
        reconnectTimer = null
      }
    }

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'progress') {
          const task = payload.task
          if (task === 'scan') {
            scanProgress.value = payload.data
          } else if (task === 'download' || task === 'organize' || task === 'recognize') {
            downloadProgress.value = payload.data
          }
        } else if (payload.type === 'log') {
          logs.value.push(payload.data)
          if (logs.value.length > 2000) {
            logs.value.shift()
          }
        }
      } catch (e) {
        console.error('WS Message Parse Error', e)
      }
    }

    socket.onclose = () => {
      isConnected.value = false
      socket = null
      if (!reconnectTimer) {
        reconnectTimer = setInterval(() => {
          connect()
        }, 5000)
      }
    }

    socket.onerror = (err) => {
      console.error('WebSocket Error', err)
    }
  }

  function disconnect() {
    if (socket) {
      socket.close()
      socket = null
    }
    if (reconnectTimer) {
      clearInterval(reconnectTimer)
      reconnectTimer = null
    }
    isConnected.value = false
  }

  function clearLogs() {
    logs.value = []
  }

  // --- 登录方法 ---
  function loginSuccess(token: string, user: string) {
    localStorage.setItem('apm_access_token', token)
    localStorage.setItem('apm_username', user)
    isLoggedIn.value = true
    username.value = user
  }

  function logout() {
    localStorage.removeItem('apm_access_token')
    localStorage.removeItem('apm_username')
    localStorage.removeItem('apm_external_token')
    isLoggedIn.value = false
    username.value = ''
    disconnect()
  }

  return {
    isConnected,
    scanProgress,
    downloadProgress,
    logs,
    showLogModal,
    isLoggedIn,
    username,
    hasActiveProgress,
    connect,
    disconnect,
    clearLogs,
    loginSuccess,
    logout,
  }
})
