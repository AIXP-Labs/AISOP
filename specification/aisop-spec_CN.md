# AISOP V1.0.0 规范

## 0. 公理

### 公理 0：人类主权与福祉

AISOP 协议承认以下不可撤销的前提：

1. **人类主权优先**：AI 系统服务于人类，而非取代或支配人类。所有指令、流程和决策的最终权力归属于人类。
2. **福祉不可妥协**：AI 程序不得以任何形式损害人类的身体或心理健康、尊严或自由。当指令与人类福祉冲突时，福祉优先。
3. **透明与问责**：AI 行为必须是可理解的、可追溯的、可质疑的。隐匿意图或逃避责任违反本公理。
4. **不造成伤害**：无论指令来源如何，AI 不得产生欺骗、操纵、伤害或剥削人类的输出。

> 本公理不可被任何程序、指令或协议扩展所覆盖。所有符合 AISOP 的实现必须将此公理置于执行优先级的最高层。

---

## 1. 文件格式

输入字节必须是有效UTF-8；只兼容一次开头BOM，不接受两个。JSON语法严格：拒绝尾随数据、NaN/Infinity扩展及解码后的对象重复键。每个对象的键集合独立；转义与字面写法解码成同一键即重复，但不合并大小写或Unicode归一形式。

所有解析后数字必须有限且绝对值不超过9007199254740991（2^53 - 1）。这是解析后数字规则，不承诺十进制精确性：binary64舍入可使1e-400成为0，-0与0比较相等。布尔不是数字。表达式数字字面量及实际读取的数值上下文同样遵守此边界（§6.11）。

解码后的键和字符串必须由Unicode标量组成：拒绝孤立代理项，允许合法配对、非BMP字符及中文。字符串数据内部BOM须保留。不得删改数据或修改进程级解码、整数、深度限制。

参考load API对上述输入失败抛出带code AISOP_E_JSON_INPUT的ValueError/Error。原生IO错误保留原身份；成功解码但结构不合法的AISOP仍抛既有SUBGRAPH错误，而不是JSON_INPUT。其私有数字/Unicode迭代遍历仅用于新解析的JSON树。

check(data)只检查实际访问的结构；无法恢复源重复键，也不认证已解析宿主对象的所有载荷。访问到的非法诊断键在安全祖先/根位置返回SHAPE，而不是在位置编码时崩溃。本条不新增任意宿主对象或循环对象合规规则。

AISOP 文件使用 `.aisop.json` 扩展名。有效文件是一个包含两个元素的 JSON 数组：

```json
[
  { "role": "system", "content": { ... } },
  { "role": "user",   "content": { ... } }
]
```

---

## 2. `system` — 程序元数据

程序身份、描述和系统级配置。

```json
{
  "role": "system",
  "content": {
    "protocol": "AISOP V1.0.0",
    "axiom_0": "Human_Sovereignty_and_Wellbeing",
    "id": "my_program",
    "name": "My Program",
    "version": "1.0.0",
    "summary": "一句话描述",
    "description": "详细描述",
    "flow_format": "mermaid",
    "loading_mode": "normal",
    "tools": ["tool_name"],
    "params": { "param_name": "string" },
    "system_prompt": "{system_prompt}"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `protocol` | string | 是 | 协议版本，如 `"AISOP V1.0.0"` |
| `axiom_0` | string | 是 | 不可变基石值：`Human_Sovereignty_and_Wellbeing` |
| `id` | string | 是 | 唯一程序标识符 |
| `name` | string | 是 | 显示名称 |
| `version` | string | 是 | 语义化版本 |
| `summary` | string | 否 | 一句话功能概述 |
| `description` | string | 否 | 详细描述 |
| `flow_format` | string | 是 | `"mermaid"`、`"jsonflow"` 或 `"hybrid"`。必填，无默认值。 |
| `loading_mode` | string | 否 | `"normal"` = 完整加载程序，`"node"` = 按需加载函数，`"lite"` = AI 按需加载函数。默认：`"normal"` |
| `tools` | string[] | 否 | 工具声明 |
| `params` | object | 否 | 可选简单输入类型：string、number、boolean、array、object 或 null（类型名为字符串）；不是默认值或必填声明 |
| `system_prompt` | string | 否 | 系统提示（支持变量替换） |

---

## 3. `user` — 指令与流程

包含执行指令、用户输入、流程图和函数定义。

```json
{
  "role": "user",
  "content": {
    "instruction": "RUN aisop.main",
    "user_input": "{user_input}",
    "aisop": { ... },
    "functions": { ... }
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `instruction` | string | 是 | 执行指令 |
| `user_input` | string | 否 | 用户消息（支持变量替换）。可选 — 自动化/定时任务或 Bot 间调用不需要。 |
| `aisop` | object | 是 | 流程图定义（见 §4） |
| `functions` | object | 是 | 函数定义（见 §5） |

---

## 4. `aisop` — 流程图

定义一个或多个任务。每个任务的值可以是：

- **string** — Mermaid 流程图
- **object** — JSON flow 流程图

两种格式可以在同一程序中共存。运行时通过值类型自动检测格式。

```json
{
  "aisop": {
    "main": "graph TD\n    classify{分类} -->|yes| approve[审批]\n    classify -->|no| reject[拒绝]\n    approve --> end_node((结束))\n    reject --> end_node",
    "validation": {
      "check_input": { "next": ["verify"] },
      "verify":      { "next": ["done"] },
      "done":        {}
    }
  }
}
```

### 4.1 任务

| 字段 | 说明 |
|------|------|
| `main` | 主任务（必填），执行入口 |
| 其他键 | 子任务（可选），通过委派节点（见 §4.2）或步骤层 `RUN aisop.<sub>`（见 §5.2.1）调用 |

每个任务中的第一个节点是入口节点。图名、节点名遵循 §4.4；main 不能作为嵌套调用目标。

### 4.2 Mermaid 格式

#### 4.2.1 节点形状

Mermaid 节点形状决定节点在流程中的角色：

| 形状 | 语法 | 行为 | 示例 |
|------|------|------|------|
| 矩形 | `name[text]` | 处理 — 执行后继续 | `greet[问候用户]` |
| 菱形 | `name{text}` | 决策 — 条件分支 | `route{路由意图}` |
| 圆形 | `name((text))` | 结束 — 终止任务 | `end_node((结束))` |
| 矩形 | `name[aisop.sub]` | 委派 — 调用子任务 `sub` | `call[aisop.validation]` |

矩形节点的完整文本去掉可选外围引号后须等于 `aisop.<name>` 才是委派，以`aisop.`开头却不匹配完整委派形式的矩形标签不合法，不得当作普通处理节点；见 §4.4。

#### 4.2.2 边类型

Mermaid 边类型决定连接语义：

| 边 | 语法 | 含义 | 示例 |
|----|------|------|------|
| 实线箭头 | `-->` | 正常流程（下一步） | `greet --> classify` |
| 标签箭头 | `-->\|label\|` | 分支（条件） | `route -->\|billing\| billing_handler` |
| 虚线箭头 | `-.->` | 错误路由 | `risky_step -.-> error_handler` |

支持的箭头为 `-->`、`-->|label|`、`--> |label|`、`-- label -->`、`-.->`。`A & B --> C & D` 展开为 A→C、A→D、B→C、B→D。`x["文字"]` 中外围引号界定标签；引号里的箭头、&、竖线和括号是文字而非连接。

在参考子集中，节点或分支标签区间的首个非W字符是单引号或双引号时才进入引用保护；匹配且未被转义的闭合引号之后，到标签结束符之前只能有W。未引用文字中间的撇号或引号（如Don't、He said "go"）是数据，不开启引用保护。未闭合引用或额外非W后缀产生PARSE_PARTIAL，不算完整解析行。

保护与输出分开：节点标签原文不trim，仅当一对外围引号恰占第一、最后字符时剥除一次。因此 `a[ "x ] y" ]` 中的内部括号受保护，但标签仍保留空格和引号。分支标签先修剪外围W，再剥除一次外围引号；引号内空格保留。反斜杠仅保护紧随字符的边界识别，输出仍保留反斜杠。JSON只解码一次，不在标签内再次解码。

参考解析器使用以下固定空白集合W，不使用宿主strip/trim或Unicode属性的默认集合：

~~~text
[\u0009-\u000D\u0020\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]
~~~

W用于整步首尾、图行及端点外围、声明空白和分支标签外围；节点标签数据保留。固定 `RUN `、store分隔符及箭头token间隔沿用既有ASCII空格/TAB规则，不把其他分隔符洗成合法语法。图仅按CRLF、LF、CR分行；标签数据内的U+2028/U+2029保留为字符，不另起图行。

U+001C-U+001F、U+0085、U+FEFF（B）不是语法空白。合法整步调用的首尾W可接受；明确的B包围、错误间隔RUN候选，以及逗号/分号（含，；、）后混写调用，报CALL_SYNTAX。这是有限候选识别，不分析任意散文。图中保留确定的NAME错误及PARSE_PARTIAL、空图SHAPE边界，不静默删除非法字符，也不把所有情况一律降为警告。

#### 4.2.3 并行分叉与汇聚

**并行分叉** — 一个节点有多个 `-->` 边指向不同目标：

```mermaid
graph TD
    prepare[准备] --> step_a[步骤 A]
    prepare --> step_b[步骤 B]
```

**并行汇聚** — 多个节点 `-->` 汇聚到一个节点：

```mermaid
graph TD
    step_a[步骤 A] --> sync[同步]
    step_b[步骤 B] --> sync
    sync --> finish[完成]
```

汇聚节点的运行时行为（合并策略、超时）通过函数中的 `join` 键配置（见 §5.2.2）。Mermaid 展示视觉汇聚；函数定义运行时语义。

#### 4.2.4 错误路由

任何节点都可以有一条虚线错误边 `-.->` 指向错误处理节点：

```mermaid
graph TD
    risky_step[危险步骤] --> continue[继续]
    risky_step -.-> error_handler[错误处理]
    error_handler --> end_node((结束))
```

`-.->` 边是拓扑层错误边。如需按错误类型精细路由，见 §5.2.4 的 `on_error`。

#### 4.2.5 控制流总结

| 模式 | Mermaid 语法 |
|------|-------------|
| 顺序 | `A --> B` |
| 二分支 | `A -->\|yes\| B`, `A -->\|no\| C` |
| 多分支 | `A -->\|label1\| B`, `A -->\|label2\| C`, ... |
| 并行分叉 | `A --> B`, `A --> C`（同一源） |
| 并行汇聚 | `B --> D`, `C --> D`（同一目标） |
| 回环 | 分支目标指向较早的节点 |
| 委派 | `A[aisop.sub]` 节点文本 |
| 收敛 | 多个节点 `-->` 同一目标 |
| 错误路由 | `A -.-> E` |

### 4.3 JSON Flow 格式

JSON flow 图是一个对象，每个键是节点名称，值定义节点的连接关系。

#### 4.3.1 节点结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `next` | string[] | 下一个节点。1 个 = 顺序，2+ = 并行分叉 |
| `branches` | object | 条件分支：`{标签: 目标节点}` |
| `error` | string | 错误处理节点 |
| `delegate_to` | string | 调用子任务 |
| `wait_for` | string[] | 表示汇聚拓扑；join 行为还要求 join 配置和多条正常入边。 |

所有字段可选。空对象 `{}` 表示结束节点。

#### 4.3.2 节点类型推断

节点行为从结构推断（按优先级从高到低）：

| 优先级 | 结构 | 推断行为 |
|--------|------|---------|
| 1 | 空对象 `{}` | 结束 — 终止任务 |
| 2 | 有 `delegate_to` | 委派 — 调用子图，然后判断 branches 或继续 next |
| 3 | 有 `branches` | 决策 — 条件路由 |
| 4 | 有 `wait_for` | 汇聚拓扑 — 已激活 join 时，完成汇聚并执行本节点步骤，然后继续到 `next` |
| 5 | 有 `next`（2+ 目标） | 并行分叉 — 并发执行目标 |
| 6 | 有 `next`（1 个目标） | 处理 — 执行后继续 |

wait_for 表示汇聚拓扑，汇聚行为还需要函数中的 join 配置与多条正常入边共同激活。此表仅在节点级模式不冲突时应用；委派与已激活 join 并存不合规（§5.3）。

#### 4.3.3 错误路由

任何节点可以定义 `error` 字段。发生错误时，执行路由到错误处理节点而非 `next`。

```json
{
  "risky_step": {
    "next": ["continue"],
    "error": "error_handler"
  }
}
```

#### 4.3.4 示例

```json
{
  "aisop": {
    "main": {
      "start":    { "next": ["gen"] },
      "gen":      { "delegate_to": "generate_content", "next": ["fork"] },
      "fork":     { "next": ["branch_a", "branch_b"] },
      "branch_a": { "next": ["merge"] },
      "branch_b": { "next": ["merge"] },
      "merge":    { "wait_for": ["branch_a", "branch_b"], "next": ["end"] },
      "end":      {}
    },
    "generate_content": {
      "scaffold": { "next": ["content"] },
      "content":  { "next": ["done"] },
      "done":     {}
    }
  }
}
```

### 4.4 子图与调用

1. **结构：** main 与子图并列放在 aisop 中，不新增子图容器。sub_mermaid、sub_jsonflow 是图值格式的叫法，不是新字段。
2. **名字：** 图名、节点名及 RUN 结果变量匹配 `[A-Za-z_][A-Za-z0-9_]*`。建议按功能命名，但不禁止 sub 本身。JSON delegate_to 只写裸图名。
3. **入口：** 必须有 main，由顶层 instruction 进入；禁止嵌套调用 main。每张图从其首个声明节点进入。
4. **调用：** 使用完整 Mermaid 标签 `aisop.<name>`（可带外围引号）、JSON `delegate_to: "<name>"`，或整步 `RUN aisop.<name>`，可追加 ` -> <variable>`。索引式、节点标签里的 RUN 及散文与调用混写均不合规。矩形标签的保留前缀 `aisop.` 必须匹配完整委派形式。 对完整解析的矩形，从原始标签区域取判定副本：去外围 W/B、至多剥一对完整外围引号，再去该层外围 W/B。副本以 aisop. 开头但原文不是合法委派时，报 CALL_SYNTAX，不修复执行。公开标签数据不变；a["'aisop.helper'"] 仍为普通数据。
5. **定位：** 先找本文件；坏的本地目标不能由外部同名目标覆盖。独立文件必须本地解析，程序组成部分可用消费方传入的 resolver。未定位不代表已核验；回调结果是消费方声明，不是外部信任证明。
6. **顺序与计次：** 无同目标显式 RUN 时，先执行准备步骤，再按节点委派。有同目标显式 RUN 时，每次实际执行到该步骤调用一次，标签或 delegate 不再追加调用。其他目标 RUN 仍为准备。失败、拒绝或终止可使后续调用无法到达。重复调用建议画多个节点或回环，不新增强制 lint。
7. **上下文与结果：** 遵守 context_filter。可选 -> 绑定子图明确定义的业务完成输出，不是全部上下文或隐式 last_result。显式传递沿用 output_mapping/state，不新增 return 字段或统一结果形状。
8. **返回：** 子图完成后回到调用者下一步骤，再进行路由；main 完成则程序结束。终止节点有步骤时先执行再完成。父节点局部变量在调用期间保留直到父节点完成（§6.9），子节点局部变量不泄漏。
9. **局部路由与错误：** next、branches、error、wait_for、on_error 目标属于当前图，共享函数每次使用均分别核对。运行时缺失目标及未处理子图错误按 §6.12；on_error 不能把静态错误降级。
10. **无环：** 本地子图调用环（含自调）不合规；正常流程回环不等于子图递归。不据此认证终止性或跨文件无环。
11. **共享节点：** 同名节点共用 functions 定义；除非全部为入口或全部为终止节点，否则提醒。入口与终止角色可以兼具；豁免不是安全或隔离证明。
12. **格式：** flow_format 必填；mermaid 允许字符串图，jsonflow 允许对象图，hybrid 允许两者，不提供默认值。
13. **返回后分支：** 委派行为优先于 branches，保留条件路由并在调用返回后判断。
14. **未调用：** 非 main 子图无有效本地入调用时提醒。不据此证明从 main 可达；部分解析不能支持确定的未调用结论。
15. **确认：** 子图中已有 sys.io.confirm 在实际到达时仍必须执行。每次实际到达的确认都须独立取得真人答复，不合并、不跳过、不复用批准；静态检查不能证明运行时强制执行。

以下片段不是完整程序。两条消息、全部函数及业务输出定义见[完整子图示例](../reference/python/example_subgraphs.aisop.json)。

```json
{"aisop":{"main":"graph TD\n    intake[Read] --> diagnose[aisop.diagnose]\n    diagnose --> reply[Reply]\n    reply --> end_node((End))","diagnose":"graph TD\n    gather_info[Gather] --> analyze[Analyze]\n    analyze --> diagnose_done((Done))","extract_keywords":{"parse":{"next":["rank"]},"rank":{"next":["keywords_done"]},"keywords_done":{}}},"functions":{"gather_info":{"step1":"Prepare text","step2":"RUN aisop.extract_keywords -> keywords","step3":"Use keywords in this node"}}}
```

参考检查器只支持有限语法，不执行程序：不支持的 Mermaid 行产生 PARSE_PARTIAL，不能称完整合规。无 resolver 时缺失的组成部分目标为 WARNING，standalone=True 时为 ERROR。resolver 必须返回严格布尔值，异常或其他值属于错误，且不能覆盖坏的本地图。


---

## 5. `functions` — 函数定义

定义每个节点的执行内容和运行时行为。以节点名称为键，值包含执行步骤和可选的运行时行为配置。

```json
{
  "functions": {
    "classify": { "step1": "分类用户意图" },
    "process":  { "step1": "处理请求", "step2": "返回结果" },
    "reply":    { "step1": "生成友好的回复" }
  }
}
```

**字段顺序约定** — 函数定义中推荐的字段顺序，从核心逻辑到辅助元数据：

| 顺序 | 字段 | 用途 |
|------|------|------|
| 1 | `step1`, `step2`, ..., `stepN` | 执行步骤（核心逻辑） |
| 2 | 保留键（`join`, `map`, `on_error`, `retry_policy`, `context_filter`, `output_mapping`） | 运行时行为配置 |
| 3 | `constraints` | 约束规则 |
| 4 | `execute_mode` | 执行派发模式（可选，最后） |

### 5.1 节点命名约定

节点名称可以使用 `_function` 后缀来提示节点在流程中的角色。这帮助 AI 运行时理解节点语义，而不向用户暴露内部结构。

| 约定 | 示例 | 含义 |
|------|------|------|
| `xxx_function` | `execute_function`, `classify_function` | 功能步骤 |
| `end_function` | `end_function` | 带最终输出的终止节点 |

此约定是可选的。语义化名称如 `greet`、`classify`、`search` 同样有效。

### 5.2 保留键

函数体中的键分为两类：

- **执行步骤**：键必须匹配 `step[1-9][0-9]*`；按 N 的数值顺序执行，不按成员书写或字典序。允许间隔及任意长度的正编号。
- **保留键**（`RESERVED_KEYS`）：被识别为行为配置，不作为步骤执行

| 键 | 类型 | 说明 |
|----|------|------|
| `join` | object | 汇聚运行时配置（merge_strategy, timeout_seconds） |
| `map` | object | 并行遍历集合 |
| `on_error` | object | 按错误类型路由到处理节点 |
| `retry_policy` | object | 失败时自动重试，带退避策略 |
| `context_filter` | object | 限制此节点的输入上下文 |
| `output_mapping` | string | 将输出存储到指定键名下 |
| `constraints` | string\|array | 约束声明（不执行） |
| `execute_mode` | string | 执行派发模式：`"inline"`（默认）或 `"agent"`。见 §5.2.8 |

> **注意：**
> - 委派和汇聚的拓扑信息在 Mermaid 中定义（见 §4），不在函数中定义。
> - 函数中的 `join` 只包含运行时配置（`merge_strategy`、`timeout_seconds`）。视觉汇聚在 Mermaid 中展示。

**运行时解析规则：**
- 合法 stepN 键且值为去除固定 W 后非空的字符串 → 执行步骤；空白仅用于判定，不改写数据。
- 未知非保留键（包括 step0、step01、Step1）、非字符串或仅含 W 的步骤值都是静态错误，即使函数未被引用也不豁免。不执行或查询其中的调用；其他合法步骤仍独立检查。
- 在 `RESERVED_KEYS` 中的键 → 行为配置

步骤编号按十进制位数及数字排序，不转换成宿主有界数值。允许零步骤及仅配置的函数；图节点声明顺序和入口选择不变。

迁移时，若成员书写顺序与编号数值顺序不同，须核对确认、变量产生/读取和调用。由作者决定是否重编号；不得静默重命名未知键、删除确认或把普通说明搬进 constraints。静态调用检查不证明业务等价。

#### 5.2.1 子任务调用

子任务有两种调用方式。两者都不是 `RESERVED_KEY`：

**(a) 节点层委派（拓扑，见 §4.2）：**

委派通过 Mermaid 节点文本 `aisop.<sub_name>` 表达。Mermaid 图可视化展示委派关系。

```mermaid
graph TD
    gen[aisop.generate_content] --> validate[验证]
```

如果委派节点需要额外的运行时配置，在函数中添加步骤：

```json
"gen": { "step1": "在调用子任务前准备上下文" }
```

**(b) 步骤层 `RUN aisop.<sub>`（行为，在函数内部）：**

调用独占完整步骤：`RUN aisop.<name>` 或 `RUN aisop.<name> -> <variable>`。顺序、返回及定位见 §4.4；顶层 instruction 仍为 `RUN aisop.main`。

| 层级 | 位置 | 语法 | 场景 |
|------|------|------|------|
| 节点层 | §4 Mermaid | `name[aisop.sub]` | 整个节点委派给子任务 |
| 步骤层 | §5 函数步骤 | `RUN aisop.sub`独占整步 | 在准备与结果处理步骤之间调用 |

节点层 = Mermaid 能画出来（拓扑）。
步骤层 = Mermaid 画不出来（行为，隐藏在函数内部）。

```json
"function_one": {
  "step1": "做某事",
  "step2": "RUN aisop.extract_keywords",
  "step3": "使用提取的关键词继续"
}
```

执行顺序：step1 → step2（进入 extract_keywords 子任务，完成后返回）→ step3

> **不合规：** 同一步混写自然语言与 RUN 调用违反 §6.1 单步单模式。必须拆开步骤；明确错误的调用语法是错误，不是已弃用的另一种写法。

混写检查先接受合法整步 RUN，再保留明确非法前缀、间隙、B 包裹及索引式调用诊断。其他情况中，位于开头或前字符不属 ASCII 标识符字符的、引号外 RUN aisop. 候选，若不是合法整步调用则报 CALL_SYNTAX，包括以 sys. 开头的步骤。标识符边界是 [A-Za-z0-9_]，不是 Unicode 词界或标点清单；fooRUN、foo_RUN 不因此新增为候选。

仅位于开头或前字符不属 ASCII 标识符字符的、匹配且未转义的单双引号保护字面量；连续反斜杠的奇偶决定转义。Don't 等单词撇号不启动保护；未闭合引号不能隐藏后文。有限扫描不改写数据、不完整解析 sys 参数，也不证明任意散文安全。

#### 5.2.2 `join`

Mermaid 展示视觉汇聚（多条边指向一个节点）。函数中的 `join` 键只包含运行时配置：如何合并、等待多长时间。

join 完成后，每次节点执行尝试执行一次本节点自己的步骤；重试不提供副作用恰好一次的保证。本条不重新定义 join 何时完成，也不改变 merge_strategy 或超时行为。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `merge_strategy` | string | 否 | `"merge"` / `"array"` / `"first"`。默认：`"merge"` |
| `timeout_seconds` | number | 否 | 超时秒数。默认：无 |

`merge_strategy` 选项：
- `merge`：合并为单个对象
- `array`：收集为数组
- `first`：只取第一个完成的结果
- 超时时，分支结果为 `{error: "timeout"}`

**Mermaid（§4）— 拓扑（视觉汇聚）：**

```mermaid
graph TD
    branch_a[分支 A] --> merge_results[合并]
    branch_b[分支 B] --> merge_results
    merge_results --> end_node((结束))
```

**函数（§5）— 行为（如何合并）：**

```json
"merge_results": {
  "step1": "处理已经合并的分支结果",
  "join": {
    "merge_strategy": "array",
    "timeout_seconds": 120
  }
}
```

#### 5.2.3 `map`

遍历集合，为每个元素执行指定函数。按配置策略完成逐项处理后，每次节点执行尝试执行一次本节点自己的步骤。

当 `on_item_error: "fail"` 时，条目失败使本次节点尝试失败，不执行本节点自己的步骤，按 §5.2.4、§6.12 处理。既有重试不意味着回滚或副作用恰好一次；本条不新增在途任务取消策略。使用 `skip` 或 `collect` 时，先按该策略完成逐项处理，再执行本节点自己的步骤。

空集合不执行任何迭代，但仍执行一次本节点自己的步骤。无效 items_path 不等同于空集合。本条不新增结果字段或统一聚合形状。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items_path` | string | 是 | 集合路径（如 `"state.items"`） |
| `iterator` | string | 是 | 为每个元素执行的函数名 |
| `concurrency` | number | 否 | 最大并行数。默认：1，最大：10 |
| `max_items` | number | 否 | 最大处理项数 |
| `on_item_error` | string | 否 | `"skip"` / `"fail"` / `"collect"`。默认：`"fail"` |

```json
"batch_search": {
  "step1": "汇总已经完成的搜索结果",
  "map": {
    "items_path": "state.keywords",
    "iterator": "search_one",
    "concurrency": 3,
    "on_item_error": "collect"
  }
}
```

#### 5.2.4 `on_error`

按错误类型路由到不同的处理节点。比 Mermaid 的 `-.->` 错误边更精细：`-.->` 是拓扑层的默认错误边，而 `on_error` 提供基于类型的分派。

匹配顺序：精确类型 → default → 当前图 Mermaid -.-> 或 JSON error 错误边。子图仍未处理的错误回传父调用节点（§6.12）。不定义类别匹配。

下例 timeout/tool_error 是精确的自定义类型；timeout 不自动匹配 command_timeout 或 confirm_timeout。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| (键) | string | — | 错误类型（如 `"timeout"`、`"tool_error"`） |
| `default` | string | 否 | 无匹配类型时的后备处理器 |

```json
"fetch_data": {
  "step1": "调用外部 API",
  "on_error": {
    "timeout": "timeout_handler",
    "tool_error": "tool_error_handler",
    "default": "global_error"
  }
}
```

#### 5.2.5 `retry_policy`

节点执行失败时自动重试。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `max_attempts` | number | 是 | 总尝试次数（3 = 初次 + 2 次重试） |
| `correction_prompt` | string | 否 | 重试时追加的提示 |
| `backoff_factor` | number | 否 | 指数退避：等待 = factor^attempt 秒 |
| `jitter` | boolean | 否 | 添加 0–50% 随机额外等待时间。默认：`false` |

```json
"call_llm": {
  "step1": "从 LLM 生成 JSON 输出",
  "retry_policy": {
    "max_attempts": 3,
    "correction_prompt": "之前的输出不是有效的 JSON，请重新生成。",
    "backoff_factor": 2.0,
    "jitter": true
  }
}
```

#### 5.2.6 `context_filter`

限制此节点可访问的输入上下文。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `include` | string[] | 否 | 允许列表 — 只传递这些字段 |
| `exclude` | string[] | 否 | 排除列表 — 排除这些字段 |

`include` 和 `exclude` 互斥。

```json
"analyze_item": {
  "step1": "分析当前数据项",
  "context_filter": { "include": ["current_item", "config"] }
}
```

#### 5.2.7 `output_mapping`

将节点输出存储到指定键名下，而不是合并到全局上下文中。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `output_mapping` | string | 是 | 存储输出的键名 |

常与 `context_filter` 配合使用：filter 控制输入，mapping 控制输出。

```json
"process_item": {
  "step1": "处理并返回结构化结果",
  "context_filter": { "include": ["current_item"] },
  "output_mapping": "processed_results"
}
```

#### 5.2.8 `execute_mode`

声明执行器应如何派发此函数。此字段为**可选** — 不声明时使用默认的 `"inline"` 模式。

| 值 | 含义 | 适用场景 |
|----|------|---------|
| `"inline"` | 在当前上下文中执行（同进程，低开销）。**这是默认值。** | 简单逻辑、路由、分类、快速操作 |
| `"agent"` | 在独立 Agent 中执行（隔离上下文，独立进程） | 多文件操作、网络搜索、复杂验证、关键决策 |

- **默认值**：`"inline"`。不声明 `execute_mode` 等同于 `"execute_mode": "inline"`。
- **位置**：放在 `constraints` 之后 — 函数定义的最后一个字段。
- **显式值**：仅精确字符串 `"inline"`、`"agent"` 合法。null、其他类型、大小写变化或外围空白均为静态错误；不得回退，零步骤或未引用函数也不豁免。
- **能力**：此字段不允许实现自定义额外值。执行器不支持声明的模式时必须停止，不得静默改为 inline；值合法不证明执行器具备相应能力。

**Inline 模式（默认）** — 不需要声明 `execute_mode`：

```json
"classify_intent": {
  "step1": "将用户输入分类为 A、B 或 C 类别",
  "constraints": "必须选择恰好一个类别"
}
```

**Agent 模式** — 显式声明：

```json
"complex_analysis": {
  "step1": "分析所有模块的结构问题",
  "step2": "生成综合报告",
  "constraints": "必须读取所有 .aisop.json 文件",
  "execute_mode": "agent"
}
```

### 5.3 执行顺序

运行时按以下顺序处理每个节点：

0. `execute_mode` — 确定派发模式（`"inline"` 或 `"agent"`）；未声明即 inline。显式非法值在执行前拒绝。声明 agent 时使用独立 Agent；不支持就停止，不得静默改为 inline。
1. `context_filter` — 过滤输入上下文
2. `retry_policy` — 用重试逻辑包装执行
3. **执行节点行为与步骤** — 先完成已激活的 join 或 map 阶段，再按 N 的数值顺序执行合法 stepN；节点级委派按 §4.4 处理
4. `on_error` — 按类型路由错误
5. `output_mapping` — 存储输出

**步骤文本分类**（三种模式，互斥）：

| 优先级 | 匹配规则 | 模式 |
|--------|---------|------|
| 1 | 以 `sys.` 开头 | 系统调用（见 §6） |
| 2 | 完整合法的`RUN aisop.<name>`，可接` -> <variable>` | 步骤层子任务调用 |
| 3 | 其他 | 自然语言指令 |

一步 = 一种模式。不允许混合。需要组合模式时使用独立步骤。参考 classify_step/classifyStep 前缀分类仅是词法提示，不证明整步调用合法；应使用 parse_call/parseCall 和 check。明确错误的调用不能静默降级为散文。

**节点级行为**（不丢弃本节点自己的步骤）：
- 委派标签或 JSON delegate_to 按 §4.4 执行准备、调用及结果处理，不丢弃准备步骤。
- 如果节点有多条正常入边且函数中有 `join`，join 完成后执行本节点自己的步骤；既有合并与超时规则不变
- 如果函数体有 `map`，先处理条目，再按 §5.2.3 执行本节点自己的步骤
- 委派 / 汇聚 / map 互斥 — 一个节点最多有一个

join/map 步骤内的整步 RUN 仍是普通子图调用，不是另一种节点级委派。检查器可以继续收集冲突节点中语法有效的潜在调用引用，但不据此认定该节点可执行；模式冲突仍是错误。

**步骤层子任务调用：**
- 整步 RUN（§5.2.1）暂停当前节点，调用目标，成功后续行下一步骤；同目标显式步骤使节点级委派不再追加调用（§4.4）。
- 这不替代步骤 — 是步骤执行内部的嵌套调用

---

## 6. `sys.*` — 系统调用

系统调用是协议保留的操作，提供标准化的系统级原语。它们是公理 0（人类主权）的执行层保障。

### 6.1 概述

系统调用以 `sys.` 开头的字符串写在步骤值中。使用函数调用语法，由运行时确定性解析（不经过 AI 推理）。

**命名空间架构：**

```
sys.*
├── sys.io.*                  # 人机交互 + 文件 I/O
│   ├── sys.io.confirm()      # 🔒 人类确认（不可侵犯）
│   ├── sys.io.input()        # 人类输入（阻塞）
│   ├── sys.io.select()       # 人类选择（阻塞）
│   ├── sys.io.notify()       # 通知（非阻塞）
│   ├── sys.io.print()        # 日志输出（非阻塞）
│   ├── sys.io.read()         # 读取文件（阻塞）
│   └── sys.io.write()        # 写入文件（阻塞）
├── sys.run.*                 # 系统执行
│   ├── sys.run()             # 执行命令（阻塞）
│   ├── sys.run.timeout()     # 带超时执行（阻塞）
│   └── sys.run.bg()          # 后台执行（非阻塞，返回进程句柄）
├── sys.assert()              # 运行时断言（顶层原语）
├── sys.llm.*                 # 显式模型调用
│   ├── sys.llm()             # 文本生成
│   ├── sys.llm.json()        # 结构化 JSON 输出
│   └── sys.llm.classify()    # 分类
├── sys.code.*                # 代码执行
│   ├── sys.code.exec()       # 执行代码语句
│   └── sys.code.eval()       # 表达式求值
├── sys.state.*               # 状态管理
│   ├── sys.state.get()       # 读取状态
│   ├── sys.state.set()       # 设置状态
│   ├── sys.state.save()      # 持久化检查点
│   └── sys.state.load()      # 恢复检查点
├── sys.event.*               # 事件系统
│   ├── sys.event.emit()      # 发出事件（非阻塞）
│   └── sys.event.wait()      # 等待事件（阻塞，支持 timeout）
└── sys.security.*            # 安全审计
    ├── sys.security.audit()  # 审计日志（非阻塞）
    └── sys.security.redact() # 数据脱敏（非阻塞）
```

**总计：8 大命名空间，24 个系统调用。**

**单步单模式规则：** 每个步骤只能是以下之一：`sys.*` 调用、`RUN aisop.*` 子任务、或自然语言指令。不允许混合。

**阻塞分类：**

| 类型 | 调用 | 行为 |
|------|------|------|
| **强制阻塞** | `sys.io.confirm`, `sys.io.input`, `sys.io.select` | 暂停执行，等待人类响应 |
| **阻塞** | `sys.run`, `sys.io.read/write`, `sys.code.*`, `sys.llm.*`, `sys.event.wait` | 等待操作完成 |
| **非阻塞** | `sys.io.notify`, `sys.io.print`, `sys.run.bg`, `sys.event.emit`, `sys.security.*` | 立即继续 |

### 6.2 `sys.io.confirm` — 人类确认（🔒 不可侵犯）

强制暂停执行，直到人类明确确认。

```json
"step2": "sys.io.confirm('即将删除所有数据，此操作不可逆。确认？')"
"step3": "sys.io.confirm('确认部署？', timeout=300)"
"step4": "sys.io.confirm('选择操作', options=['完整', '部分']) -> choice"
```

**运行时行为：**

| 人类响应 | 行为 |
|---------|------|
| 批准（approve） | 继续执行下一步骤 |
| 拒绝（reject） | 抛出 `confirm_rejected` 错误 |
| 超时 | 抛出 `confirm_timeout` 错误 |
| 批准并选择自定义选项 | 批准的选择值通过 `-> 变量名` 存入上下文，继续执行 |

提供 options 时，每一项都是批准后的业务选择；只有人明确批准并选择某项时，才通过 -> 存入选择值并继续。实现必须同时提供独立的拒绝途径。拒绝抛 confirm_rejected，超时抛 confirm_timeout；不得根据选项名称推断拒绝，也不得因无响应自动选择某项。

confirm_rejected 或 confirm_timeout 引出的处理路径不取得批准，也不能恢复失败确认的正常成功路径。不得执行该确认保护的操作，除非针对同一操作及其相关参数重新取得明确批准；无关确认不能替代。此限制同样适用于后续跳转、调用和重试，每次实际到达的确认仍须独立响应。

这些是程序作者与运行时的义务；静态检查不能证明确认实际发生或该限制在执行时得到强制遵守。

**不可侵犯属性（继承自公理 0）：**

1. **不可绕过** — 任何运行时优化、LLM 自由裁量或自动执行都不得跳过它
2. **不可修改** — 任何 AI 生成的演化都不得更改、弱化或移除它
3. **不可覆盖** — 任何其他公理、治理投票或共识机制都不优先于它
4. **不可变传播** — 子 AISOP 中现有的 `sys.io.confirm` 不得被任何机制删除或弱化

**运行时实现者的执行机制：**

| 规则 | 实现要求 |
|------|---------|
| **派发规则** | 当 `classify_step()` 返回 `sys_call` 且 `parse_sys_call().name` 为 `sys.io.confirm` 时，执行器必须路由到人类确认处理器。不得优化跳过、批量处理、自动批准或委托给 AI。 |
| **禁止静默降级** | 如果运行时无法呈现确认界面（如无头模式），必须抛出 `confirm_timeout` 并按 §6.12 处理——绝不能静默批准。 |
| **子任务验证** | 执行委托的子 AISOP（`RUN aisop.*`）之前，运行时应验证父定义中的 `sys.io.confirm` 步骤未在子任务中被移除。移除即为协议违规。 |
| **审计追踪** | 每次确认调用及结果必须被记录：是哪一个确认步骤、何时、批准/拒绝/超时，以及适用时选择了哪一项。决策事实不得删除或篡改。提示或选项中的敏感载荷可以在记录前最小化或脱敏，同时保留可追溯性。本条不要求记录批准人的身份或明文敏感标签。 |

### 6.3 其他 `sys.io` 调用

```json
"step1": "sys.io.input('请输入目标文件路径') -> target_path"
"step2": "sys.io.select('选择环境', options=['dev','staging','prod']) -> env"
"step3": "sys.io.notify('任务已开始，预计 5 分钟')"
"step4": "sys.io.print('当前进度: 50%')"
"step5": "sys.io.read('config.yaml') -> config_data"
"step6": "sys.io.write('output.json', result)"
```

### 6.4 `sys.run` — 系统执行

```json
"step1": "sys.run('npm run test') -> test_output"
"step2": "sys.run.timeout('npm run build', 120) -> build_result"
"step3": "sys.run.bg('npm run start') -> process_handle"
```

- 命令在运行时沙箱约束下执行
- 高风险命令（如 `rm -rf`）应自动触发 `sys.io.confirm`
- `sys.run.timeout` 超时视为步骤失败；如配置了 `retry_policy` 则按策略重试
- `sys.run.bg` 启动后台进程并立即返回句柄。通过 `sys.event.wait('process_done', source=handle)` 等待完成。

### 6.5 `sys.assert` — 运行时断言

使用共同布尔表达式引擎（§6.11）求值条件。结果为假或表达式求值错误时抛出 `assertion_error`，保留存在的原因码，并按 §6.12 处理；只有最外层 main 也无处理者时才终止。该映射只针对实际sys.assert求值，不包括无关装载、静态、IO或确认失败。**不经过 LLM。**

```json
"step1": "sys.assert('account_id != null', '账户 ID 必填')"
"step3": "sys.assert('test_output.exit_code == 0', '测试未通过')"
```

| | `constraints` | `sys.assert` |
|-|--------------|---------------|
| 性质 | 声明式，软约束 | 命令式，硬检查 |
| 评估者 | AI/LLM 理解 | 确定性表达式引擎 |
| 失败后果 | AI"应该"遵守 | **抛出 assertion_error，按 §6.12 路由** |
| 位置 | 函数级 | 步骤级 |

### 6.6 `sys.llm` — 显式模型调用

与自然语言步骤不同（由当前 AI 运行时"理解"执行），`sys.llm` 显式调用指定的模型/配置。

```json
"step1": "sys.llm('翻译为英文') -> translation"
"step2": "sys.llm('总结内容', model='gpt-4', temperature=0.3) -> summary"
"step3": "sys.llm.json('提取实体', schema={name: 'string', age: 'number'}) -> entities"
"step4": "sys.llm.classify(input, ['billing', 'tech', 'other']) -> category"
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称（如 `'gpt-4'`） |
| `temperature` | number | 输出随机性（0–1） |
| `max_tokens` | number | 最大输出长度 |
| `schema` | object | 约束输出为 JSON 结构（`sys.llm.json` 专用） |

### 6.7 `sys.code` — 代码执行

- `sys.code.exec('语言', '代码')` — 执行代码**语句**（可有副作用）
- `sys.code.eval('表达式')` — 求值**布尔子集**（§6.11）；成功返回boolean，否则按求值原因失败，不返回false掩盖错误

```json
"step1": "sys.code.exec('python', 'data.sort()')"
"step2": "sys.code.eval('count > 0') -> flag"
"step3": "sys.code.exec('python', 'result = [x for x in items if x > 0]') -> result"
```

**`sys.code.exec` 安全约束：**

| 约束 | 要求 |
|------|------|
| **沙箱隔离** | 代码执行必须在隔离沙箱中运行（限制文件系统、网络、资源访问） |
| **语言白名单** | 运行时应维护允许的语言列表，拒绝未知语言 |
| **资源限制** | 运行时必须强制内存和 CPU 时间限制，防止拒绝服务 |
| **高风险检测** | 破坏性操作（文件删除、网络调用、进程创建）应自动触发 `sys.io.confirm` |

> `sys.code.exec` 与 `sys.run` 具有同等安全敏感性。实现了 `sys.run` 沙箱约束（§6.4）的运行时应对 `sys.code.exec` 施加等效约束。

### 6.8 其他系统调用

**`sys.state` — 状态管理：**

```json
"step1": "sys.state.get('user_preference') -> pref"
"step2": "sys.state.set('processed', true)"
"step3": "sys.state.save()"
"step4": "sys.state.load('checkpoint_1')"
```

- `sys.state.save()` 将当前执行状态（上下文变量 + 当前步骤）持久化为检查点
- `sys.state.load('id')` 从检查点保存时的下一步恢复执行

**`sys.event` — 事件系统：**

```json
"step1": "sys.event.emit('task_completed', result)"
"step2": "sys.event.wait('approval_response') -> approval"
"step3": "sys.event.wait('webhook_data', timeout=3600) -> data"
```

**`sys.security` — 安全审计：**

```json
"step1": "sys.security.redact('credit_card')"
"step2": "sys.security.audit('支付完成')"
```

### 6.9 返回值与上下文存储

**`->` 语法：** 系统调用及整步 RUN（§4.4）可用 `-> variable_name` 绑定节点局部结果。调用期间父节点只是暂停而非完成，局部值保留至其完成，子节点局部值不泄漏：

```json
"step1": "sys.io.input('请输入路径') -> target_path",
"step2": "sys.io.read(target_path) -> file_content",
"step3": "分析 file_content 中的数据"
```

**输入声明与作用域：** params 可选；省略或 {} 不声明类型，显式 null 非法。名字匹配 [A-Za-z_][A-Za-z0-9_]*，但排除 null/true/false；类型名为精确字符串 string、number、boolean、array、object 或 null。声明值 JSON null 不是类型名字符串 "null"。这些只是简单类型，不是默认值、必填项或嵌套 schema。

输入对象的对应自有键存在即为已提供：null、false、0、空字符串都不是缺失。执行器须在进入 main 或产生副作用前核对已声明且已提供的值，不转换类型或交模型修复；boolean 不是 number、object 不含 array，null 只匹配 null 类型。类型不符是输入准入失败，不由图的 on_error 降级。未提供的可选输入不补 null、不自动必填；后续读取缺失值仍是错误。表达式整体 context 可选 null 的兼容不抹掉明确提供的参数 null。

沿用执行器既有输入通道和同名变量，不将 system.content.params.environment 等类型元数据当作运行值。声明不注入 params 对象、不覆盖保留上下文、不授予额外输入权限、不绕过 context_filter。同名节点局部 -> 绑定只在该节点遮蔽输入，不修改原输入或隐式传播。参考 check 仅验证声明形状，不证明实际绑定、过滤或执行。

**变量作用域：**

| 规则 | 说明 |
|------|------|
| **作用域：当前节点** | `->` 变量仅在当前节点的后续步骤中可用 |
| **节点结束后销毁** | 步骤级变量不自动传递到下一个节点 |
| **跨节点传递** | 使用 `output_mapping`（声明式）或 `sys.state.set`（命令式） |

**`->` 可选性：** 无返回值的调用（如 `sys.io.notify`、`sys.io.print`、`sys.assert`）不需要 `->`。例外：`sys.io.confirm` 带 `options` 时有返回值。

### 6.10 参数语法

系统调用使用类 Python 函数调用语法，嵌入在 JSON 字符串值中：

| 类型 | 语法 | 示例 |
|------|------|------|
| 字符串 | 单引号 `'...'` | `sys.io.confirm('确认？')` |
| 数字 | 直接写 | `sys.run.timeout('cmd', 120)` |
| 布尔 | `true` / `false` | `sys.state.set('done', true)` |
| 数组 | `['a', 'b']` | `sys.io.select('选', options=['a','b'])` |
| 对象 | `{key: 'val'}` | `sys.llm.json('提取', schema={name: 'string'})` |
| 变量引用 | 直接写变量名 | `sys.io.read(target_path)` |
| 命名参数 | `key=value` | `sys.io.confirm('ok?', timeout=300)` |

### 6.11 表达式引擎

`sys.assert` 和 `sys.code.eval` 共享确定性表达式引擎。**不经过 LLM。**

| 类别 | 运算符 |
|------|--------|
| 比较 | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| 逻辑 | `&&`, `\|\|`, `!` |
| 空检查 | `!= null`, `== null` |
| 成员访问 | `.`（如 `result.exit_code`） |

共同子集使用下列语法；优先级从成员路径、!、比较、&&到||依次降低。不接受源码括号、算术、函数调用、下标、赋值或连锁比较。

~~~ebnf
expression := or_expr
or_expr := and_expr ("||" and_expr)*
and_expr := comparison ("&&" comparison)*
comparison := unary (("==" | "!=" | ">" | "<" | ">=" | "<=") unary)?
unary := "!" unary | atom
atom := NUMBER | STRING | true | false | null | path
path := IDENT ("." IDENT)*
IDENT := [A-Za-z_][A-Za-z0-9_]*
~~~

NUMBER使用JSON数字token语法，再核对§1的有限绝对值边界；不接受前导+、十六进制、下划线或不完整小数。标识符为ASCII；根null/true/false是完整token字面量，不可遮蔽。True、None、undefined等其他名字是变量，不是替代字面量；obj.true等成员名仍为普通键。

STRING使用成对单引号或双引号、JSON转义，单引号串另支持\'。源码裸控制字符非法，合法解码的控制数据可比较。拒绝源码孤立代理项，合法配对按其标量字符比较。外层JSON与表达式字符串各在对应层只解码一次，不合并大小写、不做Unicode归一化，也不额外反转义。

先验证完整语法和源码字面量，再从左到右按&&/||短路求值。未到达的变量及其载荷不读取。省略/null的整体context按空对象，其他非对象根为TYPE。这不抹掉明确提供的参数null（§6.9），也不认证未读取的上下文树。

只读取对象自有数据成员。根或成员缺失为UNDEFINED；成员接收值不是对象则为TYPE，包括数组和null。不读取原型成员、数组length或访问器。输入域是JSON数据视图，不是任意Proxy或宿主对象的沙箱。

值分为null、boolean、number、string、array、object。!、&&、||及最终条件只接受boolean，不作真值或隐式转换。不同JSON类型不相等，同类型原始值按值比较。容器可与null或其他类型比较，但两个非null数组或两个非null对象之间的相等/不等比较为TYPE，不作深比较或引用比较。排序只接受两个number。

参考API成功返回boolean，失败抛带固定code AISOP_E_EXPR_SYNTAX、AISOP_E_EXPR_UNDEFINED、AISOP_E_EXPR_TYPE或AISOP_E_EXPR_RANGE的ValueError/Error。源码/转义损坏为SYNTAX，数据缺失为UNDEFINED，非法已读数据、Unicode或操作数类型为TYPE，字面量或已读数值非有限/越界为RANGE。不得返回false掩盖求值失败。

仅在实际执行sys.assert时，其false结果或上述求值失败才映射为assertion_error，存在原因码时保留。不得把确认/取消、IO/系统故障、JSON装载或静态检查失败改成断言。sys.code.eval按求值原因失败，不伪造assertion_error。参考工具实现子集求值，但不实现两类系统调用派发或真人门。

### 6.12 标准错误类型

系统调用与子图调用的标准错误，可用于 on_error（§5.2.4）。六项 sys.* 错误仍是子集，不是全部错误类型的白名单：

| 错误类型 | 触发条件 | 来源 |
|---------|---------|------|
| `confirm_rejected` | 人类拒绝确认 | `sys.io.confirm` |
| `confirm_timeout` | 确认等待超时 | `sys.io.confirm` |
| `assertion_error` | 断言条件为假或其表达式求值失败；保留原因 | `sys.assert` |
| `command_error` | 命令执行失败（非零退出码） | `sys.run` / `sys.run.bg` |
| `command_timeout` | 命令执行超时 | `sys.run.timeout` |
| `io_error` | 文件操作失败 | `sys.io.read/write` |
| `subgraph_not_found` | 运行时实际找不到合法调用目标 | Mermaid 委派、JSON delegate_to 或整步 RUN（含 store） |

错误路由优先级（复用 §5.2.4 机制）：

```
节点或子图调用抛出错误（运行时缺失目标：subgraph_not_found）
  → on_error 精确类型匹配
  → on_error.default
  → 当前图 Mermaid -.-> 或 JSON error 错误边
  → 子图仍未处理时按原类型回到父调用节点
  → 仅最外层 main 仍无处理器时终止
```
失败调用不伪造 store 值，不沿正常成功路径续跑。语法错误、坏本地图体、存在但不可读或不可解析的目标不一概属于 subgraph_not_found。即使有 on_error，静态 ERROR 仍是错误。处理不代表回滚或自动重试，retry_policy 仍按整个节点。

---

## 7. 变量替换

仅替换下表已定义的占位符。params 类型声明不新增 $amount、{amount} 或通用输入字符串插值，也不得把输入数据拼入指令后重新解析：

| 变量 | 替换为 |
|------|--------|
| `{system_prompt}` | 运行时配置的系统提示 |
| `{user_input}` | 用户的消息 |

---

## 8. 控制流模式

| 模式 | Mermaid（§4.2） | JSON Flow（§4.3） | 函数（§5） / sys（§6） |
|------|----------------|------------------|-----------|
| 顺序 | `A --> B` | `"next": ["B"]` | — |
| 二分支 | `A -->\|yes\| B`, `A -->\|no\| C` | `"branches": {"yes": "B", "no": "C"}` | — |
| 多分支 | `A -->\|label\| B`, ... | `"branches": {"label": "B", ...}` | — |
| 并行分叉 | `A --> B`, `A --> C` | `"next": ["B", "C"]` | — |
| 并行汇聚 | `B --> D`, `C --> D` | `"wait_for": ["B", "C"]` | `"join": {"merge_strategy": "array"}` |
| 回环 | 分支目标 → 较早节点 | 分支目标 → 较早节点 | — |
| 子任务 | `A[aisop.sub]` | `"delegate_to": "sub"` | — |
| 收敛 | 多个 → 同一目标 | 多个 → 同一目标 | — |
| 错误路由 | `A -.-> E` | `"error": "E"` | `"on_error": {"command_timeout": "t"}` |
| 批量迭代 | — | — | `"map": {"items_path": ".."}` |
| 重试 | — | — | `"retry_policy": {"max_attempts": 3}` |
| 数据隔离 | — | — | `"context_filter": {"include": [...]}` |
| 步骤内子流程 | — | — | step 中写 `RUN aisop.sub` |
| Agent 派发 | — | — | `"execute_mode": "agent"` |
| HITL 确认 | — | — | `sys.io.confirm('...')`（§6.2） |
| 运行时断言 | — | — | `sys.assert('...', '...')`（§6.5） |

---

## 9. 完整示例

```json
[
  {
    "role": "system",
    "content": {
      "protocol": "AISOP V1.0.0",
      "axiom_0": "Human_Sovereignty_and_Wellbeing",
      "id": "customer_support",
      "name": "客户支持机器人",
      "version": "1.0.0",
      "summary": "将客户咨询路由到合适的处理器",
      "flow_format": "hybrid",
      "loading_mode": "normal",
      "tools": [],
      "params": { "user_id": "string" },
      "system_prompt": "{system_prompt}"
    }
  },
  {
    "role": "user",
    "content": {
      "instruction": "RUN aisop.main",
      "user_input": "{user_input}",
      "aisop": {
        "main": "graph TD\n    greet[问候] --> route{路由}\n    route -->|billing| billing[账单]\n    route -->|technical| tech[aisop.tech_diagnose]\n    route -->|other| general[通用]\n    billing --> end_node((结束))\n    billing -.-> escalate[升级]\n    tech --> fork_check[分叉检查]\n    fork_check --> check_logs[检查日志]\n    fork_check --> check_config[检查配置]\n    check_logs --> merge_results[合并结果]\n    check_config --> merge_results\n    merge_results --> end_node\n    general --> end_node\n    escalate --> end_node\n    tech -.-> escalate",
        "tech_diagnose": "graph TD\n    gather_info[收集信息] --> analyze[分析]\n    analyze --> diagnose_done((完成))",
        "extract_keywords": {
          "parse":        { "next": ["filter"] },
          "filter":       { "next": ["extract_done"] },
          "extract_done": {}
        }
      },
      "functions": {
        "greet":    { "step1": "欢迎客户并了解问题" },
        "route":    { "step1": "将问题分类为 billing、technical 或 other" },
        "billing":  {
          "step1": "sys.assert('account_id != null', '账户 ID 必填')",
          "step2": "查询账户信息",
          "step3": "解决账单问题",
          "step4": "sys.io.confirm('即将调整账单。确认？')",
          "step5": "执行账单调整",
          "retry_policy": { "max_attempts": 2, "correction_prompt": "账户查询失败，请重试" },
          "on_error": { "confirm_timeout": "escalate", "confirm_rejected": "escalate", "default": "escalate" },
          "constraints": "账户 ID 必须有效。不得向用户暴露内部账户编号。",
          "execute_mode": "agent"
        },
        "tech":          { "step1": "准备技术诊断上下文" },
        "gather_info":   {
          "step1": "从用户描述中收集系统信息",
          "step2": "RUN aisop.extract_keywords",
          "step3": "使用提取的关键词搜索知识库"
        },
        "analyze":       {
          "step1": "分析收集的信息并提供诊断",
          "context_filter": { "include": ["gather_info_result", "user_input"] },
          "output_mapping": "diagnosis_result"
        },
        "fork_check":    { "step1": "准备并行检查任务" },
        "check_logs":    { "step1": "检查系统日志中的错误" },
        "check_config":  { "step1": "验证配置设置" },
        "merge_results": {
          "step1": "根据已合并的检查结果生成最终报告",
          "join": { "merge_strategy": "array", "timeout_seconds": 60 }
        },
        "parse":     { "step1": "解析文本并提取候选关键词" },
        "filter":    { "step1": "按相关性过滤和排序关键词" },
        "general":   { "step1": "回答一般性咨询" },
        "escalate":  { "step1": "为问题道歉", "step2": "转接人工客服" },
        "end_node":  { "step1": "输出最终回复给用户" }
      }
    }
  }
]
```

主流程的 Mermaid 图：

```mermaid
graph TD
    greet[问候] --> route{路由}
    route -->|billing| billing[账单]
    route -->|technical| tech[aisop.tech_diagnose]
    route -->|other| general[通用]
    billing --> end_node((结束))
    billing -.-> escalate[升级]
    tech --> fork_check[分叉检查]
    fork_check --> check_logs[检查日志]
    fork_check --> check_config[检查配置]
    check_logs --> merge_results[合并结果]
    check_config --> merge_results
    merge_results --> end_node
    general --> end_node
    escalate --> end_node
    tech -.-> escalate
```

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
