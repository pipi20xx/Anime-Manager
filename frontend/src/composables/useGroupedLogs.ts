import { computed, type Ref } from 'vue'

export interface TaskLog {
  time: string
  level: string
  message: string
}

export interface LogGroup {
  groupTime: string
  displayTime: string
  logs: TaskLog[]
}

/**
 * 按秒级时间对任务日志分组。
 * 输入 time 格式应为 HH:MM:SS.xxx（xxx 为毫秒），
 * 同一 HH:MM:SS 的日志会被合并到同一组，组标题显示完整日期时间。
 */
export function useGroupedLogs(
  source: Ref<{ logs?: TaskLog[]; started_at?: string | null } | null | undefined>
) {
  const groupedLogs = computed<LogGroup[]>(() => {
    const item = source.value
    if (!item?.logs?.length) return []

    const datePrefix = item.started_at
      ? new Date(item.started_at).toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        }).replace(/\//g, '/')
      : null

    const groups = new Map<string, TaskLog[]>()
    for (const log of item.logs) {
      // 取 HH:MM:SS 作为分组键
      const key = log.time?.split('.')?.[0] || log.time || '--:--:--'
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(log)
    }

    return Array.from(groups.entries()).map(([groupTime, logs]) => ({
      groupTime,
      displayTime: datePrefix ? `${datePrefix} ${groupTime}` : groupTime,
      logs
    }))
  })

  return { groupedLogs }
}
