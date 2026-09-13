/**
 * 整理操作类型说明
 *
 * 根据操作类型 + 源/目标目录类型（local / cd2），返回该组合下的实际工作方式说明。
 * 文案与后端 organizer_core/executor.py 的 via 路由矩阵行为一一对应。
 */
export function getActionTypeHint(
  actionType: string,
  sourceVia: string,
  targetVia: string
): string {
  const bothLocal = sourceVia !== 'cd2' && targetVia !== 'cd2'

  switch (actionType) {
    case 'move':
      if (bothLocal)
        return '本地物理移动：文件移动并重命名到目标目录，源文件不再保留；跨设备移动失败时自动回退为复制后删除源文件。'
      return ''

    case 'copy':
      if (bothLocal)
        return '本地完整复制：文件复制并重命名到目标目录，源文件保留，完成后校验文件大小。'
      return ''

    case 'link':
      if (bothLocal)
        return '硬链接：目标与源共用同一份数据，不占额外空间；要求源和目标在同一文件系统（分区），跨盘会失败，可改用移动或复制。'
      return ''

    case 'hash_only':
      return '仅识别与记录：不移动、不复制文件，只计算 SHA1 / ED2K 并写入哈希库（云盘源通过 CD2 流式拉取计算，耗时与流量相当于完整下载一次文件）。'

    case 'cd2_move': {
      if (sourceVia === 'cd2' && targetVia === 'cd2')
        return 'CD2 移动（云→云）：纯 gRPC 服务器端操作，数据不经过本机——先在原位重命名，再移动到目标目录；源文件从云盘原位置消失。'
      if (sourceVia === 'cd2' && targetVia !== 'cd2')
        return 'CD2 移动（云→本地）：通过下载直链将云端文件流式下载到本地（免挂载），成功后删除云端源文件（删除失败会按出错处理）；直链不可用时自动回退为经 CD2 挂载复制。'
      if (sourceVia !== 'cd2' && targetVia === 'cd2')
        return 'CD2 移动（本地→云）：通过 Remote Upload 协议将本地文件分块上传到云盘（免挂载），云端确认上传完成后自动删除本地源文件；上传失败不会删除源文件。'
      return 'CD2 移动（本地挂载模式）：源/目标均为本地挂载路径，通过 CD2 API 服务器端批量移动——先在源位置重命名，再移动到目标目录；源文件从源目录消失。要求源与目标都位于已配置的 CD2 挂载目录内。'
    }

    case 'cd2_copy': {
      if (sourceVia === 'cd2' && targetVia === 'cd2')
        return 'CD2 复制（云→云）：纯 gRPC 服务器端复制到目标目录并在目标位重命名，数据不经过本机；云端源文件保留。'
      if (sourceVia === 'cd2' && targetVia !== 'cd2')
        return 'CD2 复制（云→本地）：通过下载直链将云端文件流式下载到本地（免挂载）；云端源文件保留。'
      if (sourceVia !== 'cd2' && targetVia === 'cd2')
        return 'CD2 复制（本地→云）：通过 Remote Upload 协议将本地文件分块上传到云盘（免挂载）；本地源文件保留。'
      return 'CD2 复制（本地挂载模式）：源/目标均为本地挂载路径，通过 CD2 API 服务器端批量复制到目标目录并在目标位重命名；源文件保留。要求源与目标都位于已配置的 CD2 挂载目录内。'
    }

    default:
      return ''
  }
}
