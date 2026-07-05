import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import JSZip from 'jszip'
import { appearanceApi, type AppearanceConfig } from '../api/appearance'

/** 导出文件格式版本，未来如有破坏性变更可递增 */
const EXPORT_VERSION = 1

interface AppearanceExportMeta {
  __type: 'anime-manager-appearance'
  version: number
  exported_at: string
}

/**
 * 深度合并配置（instances 整体替换，与后端逻辑保持一致）
 *
 * 该函数不假设任何具体字段名，因此未来新增的配置区块会自动被递归合并。
 */
function deepMergeConfig(base: any, override: any): any {
  const result = { ...base }
  for (const key of Object.keys(override)) {
    if (key === 'instances') {
      // instances 整体替换：前端每次都发送完整状态，
      // 深合并会导致已删除的 instance key 残留
      result[key] = override[key]
    } else if (
      result[key] && typeof result[key] === 'object' && !Array.isArray(result[key]) &&
      override[key] && typeof override[key] === 'object' && !Array.isArray(override[key])
    ) {
      result[key] = deepMergeConfig(result[key], override[key])
    } else {
      result[key] = override[key]
    }
  }
  return result
}

/**
 * 递归遍历配置对象，找出所有值为已知图片文件名的引用。
 *
 * 通用实现：不假设任何具体字段名，未来新增的图片引用字段会自动被识别。
 *
 * @param obj        配置对象（或子对象）
 * @param knownImages 后端已存在的图片文件名集合
 * @returns          被引用的图片文件名集合
 */
function collectReferencedImages(obj: any, knownImages: Set<string>): Set<string> {
  const result = new Set<string>()
  function walk(val: any) {
    if (!val || typeof val !== 'object') return
    if (Array.isArray(val)) {
      for (const item of val) walk(item)
      return
    }
    for (const key of Object.keys(val)) {
      const v = val[key]
      if (typeof v === 'string' && v && knownImages.has(v)) {
        result.add(v)
      } else if (v && typeof v === 'object') {
        walk(v)
      }
    }
  }
  walk(obj)
  return result
}

/**
 * 递归遍历配置对象，把所有匹配旧图片文件名的字符串值替换为新文件名。
 *
 * 通用实现：不假设任何具体字段名，未来新增的图片引用字段会自动被重映射。
 *
 * @param obj      配置对象（会被原地修改）
 * @param mapping  旧文件名 → 新文件名 的映射表
 * @returns        是否有字段被修改
 */
function remapImageReferences(obj: any, mapping: Map<string, string>): boolean {
  let changed = false
  if (!obj || typeof obj !== 'object') return false
  if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) {
      if (typeof obj[i] === 'string' && mapping.has(obj[i])) {
        obj[i] = mapping.get(obj[i])!
        changed = true
      } else if (obj[i] && typeof obj[i] === 'object') {
        changed = remapImageReferences(obj[i], mapping) || changed
      }
    }
    return changed
  }
  for (const key of Object.keys(obj)) {
    const val = obj[key]
    if (typeof val === 'string' && val && mapping.has(val)) {
      obj[key] = mapping.get(val)!
      changed = true
    } else if (val && typeof val === 'object') {
      changed = remapImageReferences(val, mapping) || changed
    }
  }
  return changed
}

/**
 * 外观配置导入/导出 composable（ZIP 压缩包格式，含图片）
 *
 * 设计原则：完全通用，自动适配未来新增的配置字段。
 * - 导出：将完整配置 + 所有被引用的背景图片打包为 ZIP。
 *   任何新增配置字段自动包含；图片通过递归扫描自动识别。
 * - 导入：解压 ZIP → 上传图片到目标服务器（获得新随机文件名）
 *   → 自动重映射配置中的图片引用 → 应用到表单。
 *   任何新增的图片引用字段自动被重映射。
 *
 * 使用方式：
 * ```ts
 * const { fileInput, importLoading, exportConfig, triggerImport, handleFileImport } = useAppearanceConfigIO()
 * // 导出
 * await exportConfig(form)
 * // 导入
 * triggerImport()  // 触发隐藏 file input
 * const onImportFileChange = (e: Event) => handleFileImport(e, form, preview)
 * ```
 */
export function useAppearanceConfigIO() {
  const message = useMessage()
  const fileInput = ref<HTMLInputElement | null>(null)
  const importLoading = ref(false)
  const exportLoading = ref(false)

  /** 导出配置为 ZIP 压缩包（含配置 JSON + 被引用的背景图片） */
  async function exportConfig(config: AppearanceConfig) {
    if (exportLoading.value) return
    exportLoading.value = true
    try {
      // 1. 获取后端已有图片列表
      let knownImages = new Set<string>()
      try {
        const imgRes = await appearanceApi.listImages()
        knownImages = new Set((imgRes.data || []).map(img => img.filename))
      } catch (e) {
        console.warn('获取图片列表失败，将导出纯配置', e)
      }

      // 2. 找出配置中引用的图片
      const referenced = collectReferencedImages(config, knownImages)

      // 3. 创建 ZIP
      const zip = new JSZip()
      const meta: AppearanceExportMeta = {
        __type: 'anime-manager-appearance',
        version: EXPORT_VERSION,
        exported_at: new Date().toISOString(),
      }
      zip.file('meta.json', JSON.stringify(meta, null, 2))
      zip.file('config.json', JSON.stringify(config, null, 2))

      // 4. 下载并添加被引用的图片
      let imgCount = 0
      if (referenced.size > 0) {
        const imagesFolder = zip.folder('images')!
        for (const filename of referenced) {
          try {
            const res = await appearanceApi.getImageBlob(filename)
            imagesFolder.file(filename, res.data)
            imgCount++
          } catch (e) {
            console.warn(`导出图片失败: ${filename}`, e)
          }
        }
      }

      // 5. 生成并下载 ZIP
      const blob = await zip.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      const ts = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19)
      link.download = `appearance-config-${ts}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      message.success(`配置已导出${imgCount > 0 ? `（含 ${imgCount} 张图片）` : ''}`)
    } catch (e) {
      console.error('导出外观配置失败', e)
      message.error('导出失败')
    } finally {
      exportLoading.value = false
    }
  }

  /** 触发文件选择对话框 */
  function triggerImport() {
    fileInput.value?.click()
  }

  /**
   * 将导入的配置数据应用到响应式表单。
   *
   * 通用实现：遍历合并后的所有 key，逐个写入 form。
   * - 已存在的对象区块：Object.assign 原地更新（保持响应性）
   * - instances：整体替换
   * - 未来新增区块：自动添加到 form（Vue 3 Proxy 支持动态属性）
   */
  function applyImportedConfig(form: any, imported: any) {
    // 以当前表单为基底深合并，确保导入文件中缺失的字段保留当前值
    const merged = deepMergeConfig(JSON.parse(JSON.stringify(form)), imported)
    for (const key of Object.keys(merged)) {
      const val = merged[key]
      if (key === 'instances') {
        form.instances = val || {}
      } else if (val && typeof val === 'object' && !Array.isArray(val)) {
        if (form[key] && typeof form[key] === 'object') {
          // 原地更新，保持 Vue 响应性
          Object.assign(form[key], val)
        } else {
          // 未来新增的非对象区块或新 key
          form[key] = val
        }
      } else {
        form[key] = val
      }
    }
  }

  /**
   * 处理 ZIP 文件导入。
   *
   * 流程：解压 → 读取配置 → 上传图片到后端 → 重映射图片引用 → 应用到表单
   *
   * @param event  input change 事件
   * @param form   响应式表单对象
   * @param onImported  导入成功后的回调（通常传入 preview 函数以即时预览）
   */
  async function handleFileImport(
    event: Event,
    form: AppearanceConfig,
    onImported?: () => void
  ) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    importLoading.value = true
    try {
      // 1. 加载 ZIP
      const zip = await JSZip.loadAsync(file)

      // 2. 读取配置 JSON
      const configFile = zip.file('config.json')
      if (!configFile) {
        message.error('压缩包中未找到 config.json')
        return
      }
      const configText = await configFile.async('text')
      let config: any
      try {
        config = JSON.parse(configText)
      } catch {
        message.error('config.json 解析失败')
        return
      }
      if (!config || typeof config !== 'object') {
        message.error('配置文件格式无效')
        return
      }

      // 3. 读取并上传图片，建立 旧文件名 → 新文件名 映射
      const imageEntries = Object.keys(zip.files)
        .filter(path => path.startsWith('images/') && !zip.files[path].dir)

      const imageMapping = new Map<string, string>()
      let uploadedCount = 0
      let failedCount = 0

      for (const path of imageEntries) {
        const originalName = path.replace('images/', '')
        try {
          const blob = await zip.files[path].async('blob')
          // 从 blob 创建 File 对象，需要保留扩展名以便后端校验
          const ext = originalName.match(/\.[^.]+$/)?.[0] || '.png'
          const imageFile = new File([blob], `import${ext}`, { type: blob.type || 'image/png' })
          const res = await appearanceApi.uploadImage(imageFile)
          const newName = res.data.filename
          imageMapping.set(originalName, newName)
          uploadedCount++
        } catch (e) {
          console.warn(`上传图片失败: ${originalName}`, e)
          failedCount++
        }
      }

      // 4. 重映射配置中的图片引用
      if (imageMapping.size > 0) {
        remapImageReferences(config, imageMapping)
      }

      // 5. 应用配置到表单
      applyImportedConfig(form, config)
      onImported?.()

      // 6. 提示结果
      if (uploadedCount > 0 && failedCount === 0) {
        message.success(`配置已导入（含 ${uploadedCount} 张图片），请点击「保存设置」以生效`)
      } else if (uploadedCount > 0 && failedCount > 0) {
        message.warning(`配置已导入，${uploadedCount} 张图片成功，${failedCount} 张失败，请点击「保存设置」以生效`)
      } else if (imageEntries.length > 0 && uploadedCount === 0) {
        message.warning('配置已导入，但所有图片上传失败，请点击「保存设置」以生效')
      } else {
        message.success('配置已导入，请点击「保存设置」以生效')
      }
    } catch (err) {
      console.error('导入外观配置失败', err)
      message.error('导入失败，请检查文件格式')
    } finally {
      importLoading.value = false
      if (input) input.value = ''
    }
  }

  return {
    fileInput,
    importLoading,
    exportLoading,
    exportConfig,
    triggerImport,
    handleFileImport,
  }
}
