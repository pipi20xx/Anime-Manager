/**
 * CD2 API — CloudDrive2 管理接口
 */
import { api, apiFetch } from './client'

export const cd2Api = {
  /** 获取离线（种子）任务列表 + 配额（按 CD2 路径，如账号目录） */
  getOfflineTasks: (path: string) =>
    api.get<any>(`/api/cd2/offline-tasks?path=${encodeURIComponent(path)}`),

  /** 提交离线下载链接 */
  addOfflineUrls: (body: { urls: string; to_folder: string }) =>
    api.post<any>('/api/cd2/offline-tasks/add', body),

  /** 批量删除离线任务 */
  deleteOfflineTasks: (body: { info_hashes: string[]; path: string; delete_files: boolean }) =>
    api.post<any>('/api/cd2/offline-tasks/delete', body),

  /** 重启离线任务 */
  restartOfflineTask: (body: { info_hash: string; url: string; parent_id: string; path: string }) =>
    api.post<any>('/api/cd2/offline-tasks/restart', body),

  /** 按类型清空离线任务 (filter: 0=全部 1=已完成 2=错误 3=下载中) */
  clearOfflineTasks: (body: { filter: number; path: string; delete_files: boolean }) =>
    api.post<any>('/api/cd2/offline-tasks/clear', body),

  /** 获取传输监控状态 */
  getMonitorStatus: () => api.get<any>('/api/cd2/monitor'),

  /** 获取协议文件信息 */
  getProtoInfo: () => api.get<any>('/api/cd2/proto'),

  /** 强制更新协议 */
  forceUpdateProto: () => api.post<any>('/api/cd2/proto/force-update', {}),

  /** 浏览文件目录 */
  browseFiles: (path: string, refresh = false) =>
    api.get<any>(`/api/cd2/files?path=${encodeURIComponent(path)}&refresh=${refresh}`),

  /** 新建文件夹 */
  createFolder: (body: { parent_path: string; name: string }) =>
    api.post<any>('/api/cd2/files/create-folder', body),

  /** 重命名文件/文件夹 */
  renamePath: (body: { path: string; new_name: string }) =>
    api.post<any>('/api/cd2/files/rename', body),

  /** 识别后的整理式重命名（可含子目录，自动建目录+移动） */
  organizeRename: (body: { path: string; new_relative_path: string }) =>
    api.post<any>('/api/cd2/files/organize-rename', body),

  /** 删除文件/文件夹 */
  deletePaths: (body: { paths: string[] }) =>
    api.post<any>('/api/cd2/files/delete', body),

  /** 移动/复制文件 (action: move | copy) */
  transferPaths: (body: { paths: string[]; dest_dir: string; action: 'move' | 'copy'; conflict_policy: number }) =>
    api.post<any>('/api/cd2/files/transfer', body),

  /** 上传文件到指定目录 */
  uploadFile: (path: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<any>(`/api/cd2/files/upload?path=${encodeURIComponent(path)}`, form)
  },

  /** 获取 CD2 服务器运行状态 */
  getServerInfo: () => api.get<any>('/api/cd2/server-info'),

  /** 启动远程上传会话 */
  remoteUploadStart: (body: { path: string; file_name: string; size: number }) =>
    api.post<any>('/api/cd2/upload/remote', body),

  /** 长轮询获取下一个上传任务 */
  remoteUploadNext: (uploadId: string) =>
    api.get<any>(`/api/cd2/upload/remote/${uploadId}/next`),

  /** 回传分块数据（原始字节） */
  remoteUploadData: (uploadId: string, requestId: string, chunk: ArrayBuffer | Blob) =>
    apiFetch(`/api/cd2/upload/remote/${uploadId}/data?request_id=${encodeURIComponent(requestId)}`, {
      method: 'POST',
      body: chunk,
      headers: { 'Content-Type': 'application/octet-stream' },
    }).then((r) => r as any),

  /** 取消远程上传 */
  remoteUploadCancel: (uploadId: string) =>
    api.post<any>(`/api/cd2/upload/remote/${uploadId}/cancel`, {}),

  /** 获取神医深度删除联动配置 */
  getDeepDeleteConfig: () => api.get<any>('/api/cd2/deep-delete'),

  /** 保存神医深度删除联动配置 */
  saveDeepDeleteConfig: (body: {
    enabled: boolean
    delete_preference: string
    permanent_delete: boolean
    notify_on_delete: boolean
    cleanup_empty_folder: boolean
    path_mappings: Array<{ from: string; to: string }>
  }) => api.post<any>('/api/cd2/deep-delete', body),
}
