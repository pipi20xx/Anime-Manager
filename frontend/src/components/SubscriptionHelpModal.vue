<script setup lang="ts">
import { h } from 'vue'
import { NModal, NCard, NDataTable, NText, NTag, NSpace } from 'naive-ui'

defineProps<{ show: boolean }>()
const emit = defineEmits(['update:show'])

const columns = [
  { title: '设置项', key: 'label', width: 150 },
  { title: '对应元数据标签 {tag}', key: 'tag', width: 180, render(r: any) {
    return h(NText, { code: true, type: 'info' }, { default: () => r.tag })
  }},
  { title: '含义说明', key: 'desc' },
  { title: '示例填写', key: 'example', width: 180, render(r: any) {
    return h(NText, { depth: 3 }, { default: () => r.example })
  }}
]

const data = [
  { label: '分辨率', tag: '{resolution}', desc: '资源的画面清晰度', example: '1080P, 4K' },
  { label: '制作组', tag: '{team} / {group}', desc: '发布资源的字幕组或压制组', example: 'Mikan, 喵萌奶茶屋, VCB-Studio' },
  { label: '来源', tag: '{source}', desc: '资源的介质来源', example: 'WebDL, Baha, BDRip, TV' },
  { label: '视频编码', tag: '{video_encode}', desc: '视频的压缩编码格式', example: 'H265, HEVC, H264, AVC' },
  { label: '音频编码', tag: '{audio_encode}', desc: '音频的编码格式', example: 'FLAC, AAC, OPUS' },
  { label: '字幕语言', tag: '{subtitle}', desc: '资源包含的字幕语言', example: 'CHS, CHT, GB, BIG5, JAP' },
  { label: '发布平台', tag: '{platform}', desc: '资源的首发流媒体平台', example: 'Baha, Netflix, Crunchyroll' },
]
</script>

<template>
  <n-modal :show="show" @update:show="v => emit('update:show', v)" preset="card" style="width: 800px" title="订阅过滤项填写指南">
    <n-card :bordered="false">
      <div style="margin-bottom: 20px">
        <n-text depth="3">
          订阅系统会先对 RSS 标题进行 AI/元数据识别，然后根据下表的对应关系进行筛选。<br/>
          <strong>填写技巧：</strong>支持模糊匹配，且多个关键词请用<strong>英文逗号</strong>分隔。
        </n-text>
      </div>
      <n-data-table :columns="columns" :data="data" :pagination="false" />
      
      <div style="margin-top: 24px; background: #2c2c2c; padding: 16px; border-radius: 8px;">
        <div style="font-weight: bold; margin-bottom: 8px; color: #63e2b7">💡 如何知道应该填什么？</div>
        <n-text depth="3" style="font-size: 13px">
          1. 先通过<strong>“查看内容”</strong>查看现有的 RSS 条目。<br/>
          2. 观察条目下方的彩色标签（如：S1 E05, 1080p, H265）。<br/>
          3. 如果你想只下这一类，就把标签里的文字填入订阅设置对应的格子中。
        </n-text>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
</style>
