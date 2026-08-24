import { createI18n } from 'vue-i18n'

const messages = {
  'zh-CN': {
    close: '关闭',
    common: {
      reset: '重置',
      save: '保存',
    },
    theme: {
      glassSettings: '玻璃设置',
      glassAppearance: '材质',
      glassAppearanceHint: '透明突出壁纸纹理，色调增加颜色覆盖，磨砂通过模糊扩散呈现更厚的玻璃质感。',
      glassAppearanceClear: '透明',
      glassAppearanceTinted: '色调',
      glassAppearanceFrosted: '磨砂',
      glassQuality: '质量',
      glassQualityCss: 'CSS',
      glassQualityCssHint: '仅使用 CSS backdrop-filter，GPU 占用最低。',
      glassQualityBalanced: '均衡',
      glassQualityBalancedHint: '保留水纹扩散与内容保护，GPU 占用适中。',
      glassQualityHigh: '高质量',
      glassQualityHighHint: '完整时序流场、扩散细节与内容保护，GPU 占用更高。',
      glassPreset: '方案',
      glassPresetHint: '自然均衡克制，滑移强调顺畅移动，液态增强形变与惯性。',
      glassPresetNatural: '自然',
      glassPresetGlide: '滑移',
      glassPresetLiquid: '液态',
      glassDynamicsMode: '动态效果',
      glassDynamicsModeFluid: '液态',
      glassDynamicsModeFluidHint: '增强形变与惯性，指针经过玻璃时产生向相邻表面扩散的水纹。',
      glassDynamicsModeRipple: '水纹',
      glassDynamicsModeRippleHint: '滑移强调顺畅移动，指针经过玻璃时产生扩散水纹。',
      glassDynamicsModeOff: '关闭',
      glassDynamicsModeOffHint: '不产生动态水纹效果。',
      glassMaterialTuning: '材质调节',
      glassDynamicTuning: '动态调节',
      glassTransparencyStrength: '壁纸可见度',
      glassTransmissionStrength: '透射亮度',
      glassReflectionStrength: '反射亮度',
      glassDeformationStrength: '形变强度',
      glassFlowStrength: '流动强度',
      glassTranslationStrength: '平移强度',
      glassMaterialStrengthHint: '调整玻璃材质的光学参数。',
      glassOpticalStrengthHint: '调整动态水纹的强度参数。',
    },
  },
}

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages,
})

export default i18n
