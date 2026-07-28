/**
 * 任务状态统一映射工具
 * 将后端返回的英文状态值转为中文标签 + Vuetify 颜色
 */

export interface TaskStatusInfo {
  color: string
  label: string
}

const STATUS_MAP: Record<string, TaskStatusInfo> = {
  completed: { color: 'success', label: '完成' },
  running: { color: 'info', label: '运行中' },
  error: { color: 'error', label: '错误' },
  failed: { color: 'error', label: '失败' },
  stopped: { color: 'warning', label: '已停止' },
  pending: { color: 'warning', label: '等待中' },
}

export function getStatusTag(status: string): TaskStatusInfo {
  return STATUS_MAP[status] || { color: 'grey', label: status || '-' }
}
