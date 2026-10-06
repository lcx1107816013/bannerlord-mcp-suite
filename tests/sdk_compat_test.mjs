/**
 * ★ 底座兼容性的**实证**：用**官方 MCP SDK 的 Client**（不是我们自己的客户端）
 * 去连我们这四个服务器，看能不能握手、列工具、调工具。
 *
 * ## 为什么必须这样测
 *
 * "支持所有 agent 底座"这句话**不能靠推断**。判据只能是：
 * **用一个与 DSH 无关的、官方实现的标准客户端去连**，能通才算通。
 *
 * - 本项目的 `bl_chain.py` 是**手写 stdio**（没用官方 SDK），
 *   所以"我们自己的客户端 + 我们自己的服务器"能通**不构成证据**（可能一起错）。
 * - 这里用官方 `@modelcontextprotocol/sdk` 的 `Client` + `StdioClientTransport`，
 *   它代表"任何按规范实现的底座"。
 *
 * ## 四个被测目标（全部纯 stdio）
 *
 * | # | 服务器 | 实现 |
 * |---|---|---|
 * | 1 | `bl_chain.py` | 手写 stdio（protocolVersion 2024-11-05） |
 * | 2 | `bl_mcp.py`（BlBridge） | 手写 stdio |
 * | 3 | `la_mcp.py`（审计） | 手写 stdio |
 * | 4 | Sage / Helper | 官方 SDK 自己（对照组） |
 *
 * ⚠️ 已知边界：本机沙箱对 **Node 的管道 stdio** 可能 EPERM。
 *    若如此，本脚本会**如实报告"环境不支持测试"**，而不是假装通过。
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import fs from 'node:fs'

const PY = 'D:\\Program Files\\Python312\\python.exe'
const BUN = process.env.DSH_CHAIN_BUN ||
  'C:\\Users\\LCGX\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\\bun-windows-x64\\bun.exe'

const TARGETS = [
  {
    label: 'bl_chain (手写 stdio)',
    cmd: PY,
    args: ['E:\\Document\\bannerlord-mcp-suite\\bl_chain.py'],
    cwd: 'E:\\Document\\bannerlord-mcp-suite',
    env: { DSH_CHAIN_MODE: 'meta' },
    expectTools: 5,
    call: { name: 'chain_status', arguments: {} },
  },
  {
    label: 'la_mcp (手写 stdio)',
    cmd: PY,
    args: ['E:\\Document\\bannerlord-mcp-suite\\localization-audit\\la_mcp.py'],
    cwd: 'E:\\Document\\bannerlord-mcp-suite\\localization-audit',
    env: {},
    expectTools: 2,
    call: { name: 'la_dll_strings', arguments: { module: 'RTSCamera' } },
  },
  {
    label: 'bl_mcp / BlBridge (手写 stdio)',
    cmd: PY,
    args: ['C:\\Users\\LCGX\\CodeBuddy\\20260923171333\\BlBridge\\tools\\bl_mcp.py'],
    cwd: 'C:\\Users\\LCGX\\CodeBuddy\\20260923171333\\BlBridge\\tools',
    env: { BLBRIDGE_TOOLSET: 'core+config+lab' },
    expectTools: 53,
    call: { name: 'bl_status', arguments: {} },
  },
  {
    label: 'Helper (官方 SDK，对照组)',
    cmd: BUN,
    args: ['run', 'mcp/server.ts'],
    cwd: 'F:\\Program Files\\Bannerlord.Helper',
    env: {},
    expectTools: 10,
    call: { name: 'bh_list_languages', arguments: {} },
  },
]

let pass = 0
let fail = 0
const notes = []

for (const t of TARGETS) {
  process.stdout.write(`\n=== ${t.label} ===\n`)
  const client = new Client({ name: 'sdk-compat-probe', version: '1.0.0' }, { capabilities: {} })
  const transport = new StdioClientTransport({
    command: t.cmd,
    args: t.args,
    cwd: t.cwd,
    env: { ...process.env, ...t.env },
    stderr: 'ignore',
  })
  try {
    await client.connect(transport)
    console.log('  ✅ 官方 SDK connect() 成功 —— 握手通过')

    const si = client.getServerVersion()
    console.log(`     serverInfo: ${si?.name} v${si?.version}`)

    const L = await client.listTools()
    const okN = L.tools.length === t.expectTools
    console.log(`  ${okN ? '✅' : '⚠️ '} tools/list -> ${L.tools.length} 个（期望 ${t.expectTools}）`)

    const r = await client.callTool(t.call)
    const txt = (r.content || []).map((c) => c.text || '').join('')
    const okC = r.isError !== true && txt.length > 0
    console.log(`  ${okC ? '✅' : '⚠️ '} tools/call ${t.call.name} -> isError=${r.isError} / ${txt.length} 字符`)

    if (okN && okC) pass++
    else fail++
    await client.close()
  } catch (e) {
    const msg = String(e?.message || e)
    console.log(`  ✗ 失败: ${msg.slice(0, 160)}`)
    if (/EPERM|EACCES|spawn/i.test(msg)) {
      notes.push(`${t.label}: 环境限制（非服务器问题）`)
    } else {
      notes.push(`${t.label}: ${msg.slice(0, 100)}`)
    }
    fail++
    try { await client.close() } catch {}
  }
}

console.log('\n' + '='.repeat(66))
console.log(`官方 SDK 客户端兼容性：通过 ${pass} / 失败 ${fail}（共 ${TARGETS.length}）`)
if (notes.length) {
  console.log('备注：')
  for (const n of notes) console.log('  - ' + n)
}
process.exit(fail === 0 ? 0 : 1)
