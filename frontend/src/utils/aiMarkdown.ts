/**
 * AI 对话 Markdown 渲染
 *
 * - markdown-it 关闭原始 HTML（模型/工具输出不可信，防 XSS）
 * - linkify 自动识别链接，统一 target=_blank + rel=noopener
 * - highlight.js 代码高亮；fence 块带语言标签和复制按钮
 *   （复制通过容器上的事件委托读取 code 文本，见 AiChatPanel.handleContentClick）
 */
import MarkdownIt from 'markdown-it'
import mdLinkAttributes from 'markdown-it-link-attributes'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import python from 'highlight.js/lib/languages/python'
import yaml from 'highlight.js/lib/languages/yaml'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import sql from 'highlight.js/lib/languages/sql'
import ini from 'highlight.js/lib/languages/ini'
import markdownLang from 'highlight.js/lib/languages/markdown'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('ini', ini)
hljs.registerLanguage('toml', ini)
hljs.registerLanguage('markdown', markdownLang)
hljs.registerLanguage('md', markdownLang)

const aiMarkdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
})

aiMarkdown.use(mdLinkAttributes, {
  attrs: {
    target: '_blank',
    rel: 'noopener noreferrer',
  },
})

aiMarkdown.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx]
  const code = token.content
  const lang = (token.info || '').trim().split(/\s+/)[0]
  let highlighted: string
  try {
    if (lang && hljs.getLanguage(lang)) {
      highlighted = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
    } else {
      highlighted = aiMarkdown.utils.escapeHtml(code)
    }
  } catch {
    highlighted = aiMarkdown.utils.escapeHtml(code)
  }
  const langLabel = aiMarkdown.utils.escapeHtml(lang || 'text')
  return (
    `<div class="ai-code-block">` +
    `<div class="ai-code-header"><span class="ai-code-lang">${langLabel}</span>` +
    `<button type="button" class="ai-code-copy">复制</button></div>` +
    `<pre><code class="hljs language-${langLabel}">${highlighted}</code></pre>` +
    `</div>`
  )
}

export function renderAiMarkdown(content: string): string {
  return content ? aiMarkdown.render(content) : ''
}
