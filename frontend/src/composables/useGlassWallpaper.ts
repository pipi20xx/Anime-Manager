import { ref, computed, watch, onMounted } from 'vue'
import { useThemeStore } from '@/composables/useThemeStore'
import { useEffectiveGlassSettings, applyStoredThemeCustomizerAppearance, themeCustomizerPrimaryColors } from '@/composables/useThemeCustomizer'
import { normalizeThemeMaterialAccent } from '@/utils/glassColor'
import { loadGlassWallpaperTone, DEFAULT_GLASS_WALLPAPER_TONE_PROFILE, type GlassWallpaperToneProfile } from '@/utils/glassWallpaperTone'
import { useTheme } from 'vuetify'

/**
 * 从 CSS 变量 --am-body-before-image 中提取壁纸 URL。
 * tokens.css 中定义了 url("https://www.loliapi.com/acg/pc/") 等地址。
 */
function extractWallpaperUrlFromCss(): string {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--am-body-before-image')
    .trim()
  if (!raw) return ''
  // 从 url("...") 或 url(...) 中提取实际 URL
  const match = raw.match(/url\(["']?([^"')]+)["']?\)/)
  return match ? match[1] : ''
}

/**
 * 玻璃壁纸管理：
 * 壁纸 URL 来源优先级：
 * 1. localStorage 中用户保存的 URL
 * 2. CSS 变量 --am-body-before-image（tokens.css 中定义）
 * 3. 默认 loliapi 地址
 *
 * WebGL 纹理加载需要 CORS 支持，外部壁纸通过后端 /api/appearance/wallpaper_proxy 代理。
 * 壁纸色调分析（tone profile）用于材质亮度调节。
 */
export function useGlassWallpaper() {
  const themeStore = useThemeStore()
  const vuetifyTheme = useTheme()
  const effectiveGlassSettings = useEffectiveGlassSettings()

  // 从 CSS 变量或 localStorage 获取壁纸源 URL
  const cssWallpaperUrl = extractWallpaperUrlFromCss()
  const savedWallpaperUrl = localStorage.getItem('glass_wallpaper_url') || ''
  const sourceWallpaperUrl = savedWallpaperUrl || cssWallpaperUrl || 'https://www.loliapi.com/acg/pc/'

  // WebGL 使用的壁纸 URL —— 通过后端代理避免 CORS 问题
  // 同源请求天然满足 CORS，WebGL 纹理可直接读取
  const wallpaperUrl = ref<string>(`/api/appearance/wallpaper_proxy?url=${encodeURIComponent(sourceWallpaperUrl)}`)
  const previousWallpaperUrl = ref<string>('')
  const transitionStartedAt = ref<number>(0)
  const pendingWallpaperUrl = ref<string>('')
  const pendingWallpaperRevision = ref<number>(0)
  const activateWallpaperRevision = ref<number>(0)

  // 壁纸色调 profile —— 用于材质亮度调节
  const wallpaperToneProfile = ref<GlassWallpaperToneProfile>(DEFAULT_GLASS_WALLPAPER_TONE_PROFILE)

  // 壁纸交叉淡化时长
  const TRANSITION_DURATION_MS = 1500

  const isGlassTheme = computed(() => themeStore.glassTheme === 'acg')
  const shouldRenderGlassOpticalLayer = computed(
    () =>
      isGlassTheme.value &&
      effectiveGlassSettings.value.glassQuality !== 'css' &&
      Boolean(wallpaperUrl.value),
  )

  // 玻璃材质色
  const glassMaterialTintColor = computed(
    () =>
      normalizeThemeMaterialAccent(String(vuetifyTheme.current.value.colors.primary))?.hex ??
      normalizeThemeMaterialAccent(themeCustomizerPrimaryColors[0].value)!.hex,
  )

  // 光学参数
  const opticalDeformationStrength = computed(() => effectiveGlassSettings.value.glassDeformationStrength)
  const opticalFlowStrength = computed(() => effectiveGlassSettings.value.glassFlowStrength)
  const opticalQuality = computed(() => effectiveGlassSettings.value.glassQuality)
  const opticalReflectionStrength = computed(() => effectiveGlassSettings.value.glassReflectionStrength)
  const opticalTransparencyStrength = computed(() => effectiveGlassSettings.value.glassTransparencyStrength)
  const opticalTransmissionStrength = computed(() => effectiveGlassSettings.value.glassTransmissionStrength)
  const opticalTranslationStrength = computed(() => effectiveGlassSettings.value.glassTranslationStrength)

  /** 设置壁纸源 URL（内部会自动转换为代理 URL） */
  function setWallpaperUrl(url: string) {
    if (!url) return
    const proxyUrl = `/api/appearance/wallpaper_proxy?url=${encodeURIComponent(url)}`
    if (proxyUrl === wallpaperUrl.value) return
    previousWallpaperUrl.value = wallpaperUrl.value
    wallpaperUrl.value = proxyUrl
    transitionStartedAt.value = performance.now()
    localStorage.setItem('glass_wallpaper_url', url)
    syncWallpaperCssVar(url)
    // 异步分析壁纸色调
    void loadWallpaperTone(proxyUrl)
  }

  /** 将壁纸源 URL 同步到 CSS 变量（CSS 背景使用原始 URL，不受 CORS 限制） */
  function syncWallpaperCssVar(url: string) {
    if (url) {
      document.documentElement.style.setProperty('--glass-wallpaper-url', `url("${url}")`)
    } else {
      document.documentElement.style.removeProperty('--glass-wallpaper-url')
    }
  }

  /** 异步加载壁纸色调分析结果，用于材质亮度调节 */
  async function loadWallpaperTone(proxyUrl: string) {
    try {
      const result = await loadGlassWallpaperTone(proxyUrl)
      wallpaperToneProfile.value = result.profile
    } catch {
      wallpaperToneProfile.value = DEFAULT_GLASS_WALLPAPER_TONE_PROFILE
    }
  }

  /** 初始化默认壁纸 —— 从 CSS 变量读取，经后端代理供 WebGL 使用 */
  function initDefaultWallpaper() {
    const cssUrl = extractWallpaperUrlFromCss()
    const sourceUrl = cssUrl || 'https://www.loliapi.com/acg/pc/'
    const proxyUrl = `/api/appearance/wallpaper_proxy?url=${encodeURIComponent(sourceUrl)}`
    wallpaperUrl.value = proxyUrl
    // CSS 背景层使用原始 URL（body::before 已由 tokens.css 设置）
    // 这里不覆盖 --am-body-before-image，保持 tokens.css 的原始壁纸
    // 异步分析壁纸色调
    void loadWallpaperTone(proxyUrl)
  }

  // 当切换到 ACG 主题时，应用玻璃设置并初始化壁纸
  watch(
    () => themeStore.glassTheme,
    (theme) => {
      if (theme === 'acg') {
        applyStoredThemeCustomizerAppearance()
        initDefaultWallpaper()
      }
    },
    { immediate: true },
  )

  onMounted(() => {
    if (isGlassTheme.value) {
      applyStoredThemeCustomizerAppearance()
      initDefaultWallpaper()
    }
  })

  return {
    wallpaperUrl,
    previousWallpaperUrl,
    transitionStartedAt,
    transitionDuration: TRANSITION_DURATION_MS,
    pendingWallpaperUrl,
    pendingWallpaperRevision,
    activateWallpaperRevision,
    shouldRenderGlassOpticalLayer,
    glassMaterialTintColor,
    opticalDeformationStrength,
    opticalFlowStrength,
    opticalQuality,
    opticalReflectionStrength,
    opticalTransparencyStrength,
    opticalTransmissionStrength,
    opticalTranslationStrength,
    effectiveGlassSettings,
    wallpaperToneProfile,
    setWallpaperUrl,
  }
}
