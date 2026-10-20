// 列表动态列共享工具：字段定义驱动表格列渲染

// 更新请求体：保留所有字段，空值转 null（后端 exclude_unset 下才能真正清空字段）；
// 唯一标识字段(requiredKey)为空时不发送，避免破坏必填唯一标识
export function toUpdateBody(form, requiredKey) {
  const body = {}
  for (const [k, v] of Object.entries(form)) {
    if (v === '' && k === requiredKey) continue
    body[k] = v === '' ? null : v
  }
  return body
}

// 将自定义字段(cf_*)从表单顶层收集到 extra 字典，并从顶层移除。
// 前端 DynamicFormFields 绑定 model[cf_xxx]（顶层），但后端期望 cf_* 在 extra 内。
// 空值也发送（空字符串），让后端 save_extra 清空该字段。
export function packExtra(form, fields) {
  const extra = {}
  for (const f of fields) {
    if (f.key.startsWith('cf_')) {
      extra[f.key] = form[f.key] ?? ''
    }
  }
  const body = { ...form }
  for (const k of Object.keys(body)) {
    if (k.startsWith('cf_')) delete body[k]
  }
  body.extra = extra
  return body
}

export function fieldValue(row, f) {
  const v = row[f.key]
  if (v != null && v !== '') return v
  return row.extra?.[f.key] ?? null
}

const CJK = /[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]/

// 按内容自适应列宽（类 Excel）：取表头与所有单元格最长行的宽度
export function calcColWidth(rows, f, minW = 80, maxW = 320) {
  const measure = (s) => {
    let w = 0
    for (const ch of String(s).slice(0, 50)) w += CJK.test(ch) ? 13 : 7.2
    return w
  }
  let max = measure(f.label) + 30
  for (const r of rows) {
    const v = fieldValue(r, f)
    if (v == null || v === '') continue
    for (const line of String(v).split('\n')) {
      const w = measure(line)
      if (w > max) max = w
    }
    if (max >= maxW) break
  }
  return Math.max(minW, Math.min(maxW, Math.ceil(max + 22)))
}

// 通用值比较：空值排最前(升序)，数字按大小，其余按中文拼音（数字串按数值）
export function compareValues(x, y) {
  const ex = x == null || x === ''
  const ey = y == null || y === ''
  if (ex && ey) return 0
  if (ex) return -1
  if (ey) return 1
  const nx = Number(x)
  const ny = Number(y)
  if (!Number.isNaN(nx) && !Number.isNaN(ny)) return nx - ny
  return String(x).localeCompare(String(y), 'zh-CN', { numeric: true })
}

// el-table 列排序器：按字段取值（含 extra 自定义字段）比较，
// 避免默认比较器对中文按码位排序（看起来"乱跳"）和自定义字段取不到值
export function makeSorter(f) {
  return (a, b) => compareValues(fieldValue(a, f), fieldValue(b, f))
}

// 编码型字段的显示映射：存储/过滤仍用原始值，仅筛选面板与摘要文案翻译为中文
const VALUE_LABELS = {
  ip_type: { patent: '专利', software_copyright: '软著', other: '其他' },
}

export function valueLabel(f, v) {
  return VALUE_LABELS[f?.key]?.[v] ?? v
}

// 从当前数据生成筛选项（全部不同值，按自然顺序排序；面板内可搜索）
export function makeFilters(rows, f) {
  const vals = [...new Set(rows.map((r) => fieldValue(r, f)).filter((v) => v != null && v !== ''))]
  vals.sort((a, b) => compareValues(valueLabel(f, a), valueLabel(f, b)))
  return vals.map((v) => ({ text: String(valueLabel(f, v)), value: v }))
}

const WIDE_FIELD_KEYS = new Set([
  'acknowledgements', 'notes', 'targets', 'targets_done',
  'research_direction', 'authors_raw', 'summary',
])

export function isWideField(f) {
  return WIDE_FIELD_KEYS.has(f.key) || f.key.startsWith('cf_')
}

// select字段的状态色
export function tagTypeFor(f, v) {
  if (f.key === 'status') {
    if (['在读/在职', '在研', '已授权', '已登记', '已结题'].includes(v)) return 'success'
    if (['拟录取', '毕业/出站'].includes(v)) return 'warning'
    return 'info'
  }
  if (f.key === 'degree_type' || f.key === 'category' || f.key === 'venue_type' || f.key === 'ip_type') return 'info'
  return ''
}
