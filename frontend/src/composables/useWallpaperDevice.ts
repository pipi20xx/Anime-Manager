import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import type { WallpaperDevice, WallpaperSourceDevice } from '@/api/appearance'

/**
 * 壁纸配置维度：按访问设备区分电脑端 / 移动端。
 *
 * 使用与移动端布局一致的断点（窗口宽度 < 960px 视为移动端），
 * 这样窄窗口的电脑浏览器也会拿到竖屏壁纸，视觉上更协调。
 */
export function useWallpaperDevice() {
  const { smAndDown } = useDisplay()
  return computed<WallpaperDevice>(() => (smAndDown.value ? 'mobile' : 'pc'))
}

export const WALLPAPER_DEVICE_OPTIONS = [
  { value: 'pc', label: '电脑端', icon: 'mdi-monitor' },
  { value: 'mobile', label: '移动端', icon: 'mdi-cellphone' },
] as const satisfies ReadonlyArray<{ value: WallpaperDevice; label: string; icon: string }>

/** 设备 / 来源设备的中文展示名。 */
export function wallpaperDeviceLabel(device?: WallpaperSourceDevice): string {
  if (device === 'pc') return '电脑端'
  if (device === 'mobile') return '移动端'
  return '通用'
}
