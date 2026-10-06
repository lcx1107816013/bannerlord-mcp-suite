/**
 * 用**官方 MCP SDK 自己的 zod schema** 校验 bl_chain.py 的真实协议线。
 *
 * 为什么用这个办法：本机沙箱禁止 Node 的管道 stdio（`spawn EPERM`），
 * 所以不能让官方 SDK 的 Client 直接 spawn 我们的服务器。
 * 但 SDK 对每条消息的**校验**是独立的一步 —— 所以改成：
 *   Python 抓真实协议线（capture_wire.py）→ Node 用官方 SDK 的 schema 逐条校验。
 * 这比"能不能握手"更硬：它逐字节验"我们发出的每个响应是否合规"。
 *
 * 校验对象（全部来自官方 SDK，不是我写的）：
 *   InitializeResultSchema / ListToolsResultSchema / CallToolResultSchema
 *   ToolSchema（listTools 里每个工具的 schema）
 */
import fs from 'node:fs'

const SDK = 'file:///F:/Program%20Files/BannerlordSage/node_modules/@modelcontextprotocol/sdk/dist/esm'
const {
  InitializeResultSchema,
  ListToolsResultSchema,
  CallToolResultSchema,
} = await import(`${SDK}/types.js`)

const WIRE = 'E:\\Document\\mcp-chain\\wire_capture.json'
const data = JSON.parse(fs.readFileSync(WIRE, 'utf8'))

let fails = []
let checked = 0

function validate(label, schema, payload) {
  const parsed = schema.safeParse(payload)
  checked++
  if (parsed.success) {
    return true
  }
  const issues = parsed.error.issues
    .slice(0, 6)
    .map((i) => `${i.path.join('.') || '(root)'}: ${i.message}`)
    .join(' | ')
  fails.push(`${label} schema 校验失败 -> ${issues}`)
  console.log(`   [!!] ${label}: ${issues}`)
  return false
}

for (const [key, cap] of Object.entries(data)) {
  console.log(`\n== ${key} (mode=${cap.mode}${cap.groups ? ', groups=' + cap.groups : ''}) ==`)

  // 把「请求 id -> 请求 method/params」建索引，才能判断响应该用哪个 schema
  const reqById = new Map()
  for (const s of cap.sent) {
    if (s.id !== undefined) reqById.set(s.id, s)
  }

  for (const line of cap.received) {
    let msg
    try {
      msg = JSON.parse(line)
    } catch (e) {
      fails.push(`${key}: 非 JSON 行 -> ${line.slice(0, 120)}`)
      continue
    }
    // JSON-RPC 信封基本检查
    if (msg.jsonrpc !== '2.0') {
      fails.push(`${key}: jsonrpc 字段不是 "2.0" -> ${JSON.stringify(msg).slice(0, 120)}`)
      continue
    }
    const req = reqById.get(msg.id)
    if (!req) {
      fails.push(`${key}: 响应 id=${msg.id} 找不到对应请求`)
      continue
    }
    if (msg.error) {
      fails.push(`${key}: ${req.method} 返回了协议错误 -> ${JSON.stringify(msg.error)}`)
      continue
    }

    if (req.method === 'initialize') {
      const ok = validate(`${key}/initialize`, InitializeResultSchema, msg.result)
      if (ok) {
        const t = msg.result.capabilities?.tools
        console.log(`   [ok] initialize -> serverInfo=${JSON.stringify(msg.result.serverInfo)} tools.capability=${JSON.stringify(t)}`)
      }
    } else if (req.method === 'tools/list') {
      const ok = validate(`${key}/tools/list`, ListToolsResultSchema, msg.result)
      if (ok) {
        const tools = msg.result.tools
        const names = tools.map((t) => t.name)
        const bytes = Buffer.byteLength(JSON.stringify(tools), 'utf8')
        console.log(`   [ok] tools/list -> ${tools.length} 个 / ${bytes.toLocaleString()} 字节 ≈ ${Math.round(bytes / 3.44).toLocaleString()} tok`)
        if (key === 'meta' || key === 'meta_ro') {
          console.log(`        元工具: ${names.join(', ')}`)
        }
      }
    } else if (req.method === 'tools/call') {
      const ok = validate(`${key}/tools/call(${req.params.name})`, CallToolResultSchema, msg.result)
      if (ok) {
        const text = (msg.result.content ?? [])
          .filter((c) => c.type === 'text')
          .map((c) => c.text ?? '')
          .join('\n')
        console.log(`   [ok] tools/call ${req.params.name} -> isError=${msg.result.isError === true}, ${text.length} 字节`)
        // 关键语义断言
        const target = req.params.arguments?.name
        if (target === 'no_such_tool_zz') {
          if (msg.result.isError !== true) {
            fails.push(`${key}: 未知工具竟然没报 isError`)
          } else {
            console.log(`        ★ 未知工具如实报 isError=true（不是协议错，模型能看到原因）`)
          }
        }
        if (target === 'bl_config') {
          const hiddenFail = msg.result.isError === true || text.includes('未知工具')
          if (hiddenFail) {
            fails.push(`${key}: 隐藏工具 bl_config 调用失败`)
          } else {
            console.log(`        ★ 隐藏工具 bl_config（不在 tools/list 里）经元工具仍调通 —— 无损实证`)
          }
        }
      }
    }
  }
}

console.log('\n' + '='.repeat(70))
console.log(`用官方 SDK schema 校验了 ${checked} 条响应。`)
if (fails.length) {
  console.log(`失败 ${fails.length} 项：`)
  fails.forEach((f) => console.log('  - ' + f))
  process.exit(1)
}
console.log('全部通过：bl_chain.py 发出的每一条协议消息都符合官方 MCP SDK 的 schema。')
