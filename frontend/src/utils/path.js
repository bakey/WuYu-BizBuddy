/**
 * 从任意路径/URL 里抽出文件名。
 *
 *  - 兼容 "/" 和 "\\" 分隔（Windows 路径也能处理）
 *  - 去掉 URL 的 query/hash 部分
 *  - 已经是纯文件名或空字符串时原样返回
 *
 * 例子：
 *   basename('/data/policy/大气防治法.pdf')          → '大气防治法.pdf'
 *   basename('D:\\docs\\环保\\废弃物名录.docx')       → '废弃物名录.docx'
 *   basename('https://x.com/f/abc.pdf?v=1')          → 'abc.pdf'
 *   basename('文档片段 1')                            → '文档片段 1'
 */
export function basename(source) {
  if (!source) return ''
  let s = String(source).trim()
  // 去 query / hash
  const q = s.indexOf('?')
  if (q >= 0) s = s.slice(0, q)
  const h = s.indexOf('#')
  if (h >= 0) s = s.slice(0, h)
  // 去尾部斜杠，避免 "/foo/bar/" 抽出空串
  s = s.replace(/[\\/]+$/, '')
  // 找最后一段
  const idx = Math.max(s.lastIndexOf('/'), s.lastIndexOf('\\'))
  return idx >= 0 ? s.slice(idx + 1) : s
}
