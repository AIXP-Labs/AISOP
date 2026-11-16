# 如何贡献

> ⚠️ **当前阶段的贡献政策**
>
> 我们欢迎通过 **GitHub Issues 进行讨论**。
>
> **当前不接受外部 Pull Request。** 如果您有任何建议 — bug 报告、功能想法、规范澄清或实现建议 — 请通过 Issue 描述。如果我们认为有价值，由维护者实现并在 commit/release notes 中署名感谢您。
>
> 此政策未来会重新审视。

> **阶段状态（v1.0.0）**
>
> AISOP 处于早期规范阶段。初期决策由 AIXP Labs 核心维护者做出；社区讨论窗口将随贡献者基数增长而扩大。

## 贡献方式（通过 Issue）

- **规范** — 通过 Issue 提出协议变更建议
- **参考实现** — 提议其他语言的实现（Go、Java、Rust 等）
- **文档** — 提议文档改进、教程、错别字修正
- **测试用例** — 提议新的边界情况测试场景
- **Bug 报告** — 报告规范或参考实现中的问题

## 贡献流程

1. **打开一个 Issue**，描述您的提议、Bug 或想法
2. **与维护者讨论** — 明确范围、设计和方法
3. **若被采纳**，维护者将实现该变更并在 commit/release notes 中署名感谢您

## 贡献原则

- 保持协议简洁 — 复杂性是缺陷，而非特性
- 参考库及原测试不得引入第三方运行依赖；包构建和可选文档工具另行区分
- 所有控制流模式必须有对应测试用例
- 协议变更需同步更新规范文件和参考实现

## 运行测试

维护者应从仓库根目录直接运行两套测试：

```bash
cd reference/python
python -B test_all.py
cd ../javascript
node test_all.js
```

实现改动要求两套测试均通过。静态拒绝用例命中预期错误即为用例通过；检查器通过不证明业务执行或真人确认。纯文档工作不要求重复已经记录且实现未变的测试。

### 环境要求

- 运行参考库及原测试只需要 Python 标准库或 Node.js 内置模块，不需要 pip/npm 安装。
- Python 包构建单独使用 [pyproject.toml](reference/python/pyproject.toml) 声明的 setuptools 后端，SPDX 许可证元数据目前要求 77+。
- 可选站点构建需要与 `mkdocs.yml` 兼容的 MkDocs、Material 主题和 Pymdown Extensions 环境；工具不可用或跳过构建不能写成通过。
- Python 包声明支持 Python 3.10+。仓库 CI 配置覆盖 Python 3.10～3.15、Node.js 24 以及 ubuntu-24.04 和 windows-2022。配置了矩阵不代表某次工作流已经运行成功。
- 使用上面的直接命令，不要把 `python run.py --test` 作为发布门：该 Python 包装入口没有传播测试子进程的非零退出码。

### 分享前的隐私检查

请使用合成示例，发布 Issue 或附日志前先脱敏。检查命令会输出元数据和步骤，`--prompt` 会输出构造后的完整 prompt；命令参数可能留在 shell 历史或进程列表中。不要附凭据、私钥、完整环境文件或原始私密对话。

`.gitignore` 能减少误加入，但不会移除已跟踪文件、保护本地数据或扫描公开模板中的秘密。疑似漏洞按 [SECURITY.md](SECURITY.md) 私密报告，不要在公开复现中包含敏感内容。

## 写作规范

### RFC 2119 关键词

撰写规范性内容时，请使用 [RFC 2119](https://tools.ietf.org/html/rfc2119) 定义的关键词：

- **MUST** / **MUST NOT** — 绝对要求
- **SHOULD** / **SHOULD NOT** — 强烈建议（允许有据可循的例外）
- **MAY** — 真正可选

这些关键词在规范意义上**必须**大写。

### 术语规范

- 使用 "AISOP 文件" 指代单个 `.aisop.json` 文件
- 使用 "AISOP 程序" 或 "流程程序" 指代可执行的 AISOP 定义
- "公理 0" 大写（专有名词）
- 引用图时用 "Mermaid 图" 或 "JSON Flow 图"，不要用单独的 "图"
- 用 "sys.* 调用" 指代系统调用（如 "sys.io.confirm 调用"）
- 控制流术语首字母大写：Branch（分支）、Sub-task（子任务）、Parallel（并行执行）

### 文档结构

- 每个主题文档以一段简介开头
- 字段规范用表格
- 示例代码块标注语言
- 流程与架构示意用 Mermaid 图
- 文档之间用相对链接互相引用

### 闭合签名

所有规范文档**必须**以下行结尾：

```
Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
```

## 行为准则

请保持尊重、建设性，专注于让协议对所有人更好用。

## 贡献的许可

提交 Issue 或任何其他内容（包括规范建议、Issue 中的代码片段或设计建议）即表示您同意维护者可以在 [Apache License, Version 2.0](LICENSE) 条款下使用您提交的内容，与本项目使用相同的许可证。

## 公理约束

所有贡献必须符合**公理 0：人类主权与福祉**。任何损害人类健康、尊严或自由的变更将不予受理。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AISOP V1.0.0. www.aisop.dev
