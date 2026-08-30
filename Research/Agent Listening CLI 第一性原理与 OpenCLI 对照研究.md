# Agent Listening CLI 第一性原理与 OpenCLI 对照研究

研究日期：2026-08-30
研究范围：先评估调用、发现、安装和 Agent 接入方式，再记录本轮最小实施结果；不改变 Agent Listening 的产品边界。

说明：第 5–9 节首先记录的是实施前决策基线。第 11 节是 2026-08-30
实施后的状态更新；若两处表述冲突，以第 11 节的实际检查结果为准。

## 结论先行

Agent Listening 不应接入 OpenCLI，也不应为了“更容易被 Agent 调用”增加 MCP server。

最经济且有效的产品形态是：

```text
agent-listening executable
  + one stable analyze command
  + one JSON receipt on stdout
  + artifacts on disk
  + one thin Agent Skill for discovery and reading policy
  + standard Python tool installation for PATH discovery
```

OpenCLI 是一个把网站、登录态浏览器、Electron 应用和外部二进制汇入同一命令面的 automation hub；它的 Browser Bridge、daemon、adapter/plugin system 是为不稳定网页和有状态浏览器自动化支付的复杂度，不是 Agent Listening 这种已经拥有稳定本地 CLI 的工具所缺的能力。OpenCLI 自己也把现有本地二进制视为 `external CLI`，即包装而不是重写。[OpenCLI README](https://github.com/jackwener/OpenCLI#readme)；[OpenCLI Extending guide](https://github.com/jackwener/OpenCLI/blob/main/docs/guide/extending-opencli.md)

应借鉴 OpenCLI 的四点：可发现的命令、`doctor` 预检、机器可读 envelope、compact-first/detail-on-demand。其余部分不进入 Agent Listening。

## 1. CLI 的第一性原理

CLI 的本质不是“给人看的终端界面”，而是一个稳定的操作系统进程边界：

```text
argv / environment / input file
             ↓
        deterministic process
             ↓
stdout data + stderr diagnostics + exit status + output artifacts
```

一个可被人、shell、CI 和 Agent 共同使用的 CLI，只需要把五件事做稳定：

1. **发现**：调用者能在 `PATH` 找到唯一命令，并能读取 `--help`、`--version`。
2. **输入**：参数语义明确；文件路径、模式和输出目录不依赖当前对话上下文。
3. **机器结果**：stdout 在机器模式下只承载一个有版本的结构化结果。
4. **诊断**：进度和诊断进入 stderr；失败返回非零 exit status 和可分支的 error code/type。
5. **证据持久化**：大结果写入文件，stdout 只返回小 receipt 和绝对路径。

POSIX 的 utility conventions 将 utility、option、option-argument 和 operand 定义为稳定调用语法；标准 utility 的错误诊断写入 stderr 并以非零状态退出。它也规定 `--` 用于保护可能被误解为选项的 operand。[The Open Group: Utility Conventions](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html)；[The Open Group: Utility Description Defaults](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap01.html)

Agent Listening 当前架构已经满足其中最重要的部分：`analyze AUDIO --analysis-mode ... --output-dir ... --json`、stdout 单一 receipt、stderr extractor chatter、非零错误状态、receipt-first artifact 路径。它不需要第二个协议来变成“Agent 可调用”。

### 为什么不把音频从 stdin 传入

Unix composability 不等于所有输入都必须使用 pipe。Agent Listening 的下游 extractor 需要可寻址文件，产物还要记录 source SHA-256、duration 和 provenance。对可能很大的 WAV/FLAC，绝对文件路径是更小、更可复现的 contract。组合发生在 JSON receipt 和 artifact path 上：

```bash
receipt="$(agent-listening analyze "$audio" --analysis-mode solo --output-dir "$out" --json)"
music_ir="$(printf '%s\n' "$receipt" | jq -r '.artifacts.music_ir')"
```

## 2. OpenCLI 真正解决什么

根据其 README，OpenCLI 的主要对象是网站、真实登录态 Chrome、Electron app 和多个外部 CLI；它依赖 Node、Browser Bridge extension 和本地 daemon，并通过 adapters、plugins 和 browser session primitives 建立统一命令面。[OpenCLI README](https://github.com/jackwener/OpenCLI#quick-start)

它对 Agent Listening 有价值的不是代码，而是产品原则：

| OpenCLI 做法 | 第一性原理价值 | Agent Listening 是否采用 |
|---|---|---|
| `opencli list` | 让能力可发现 | 不新增 `list`；当前只有一个正式动作，`--help` 足够 |
| `opencli doctor` | 在昂贵任务前暴露环境缺口 | 建议采用最小的 `doctor --json` |
| 每条命令返回 structured envelope | Agent 可按字段和 code 分支 | 已由 versioned receipt 实现，应继续稳定 |
| compact output first、full payload on demand | 避免上下文浪费 | 已由 receipt → Music IR → JAMS → stems/symbols → raw 实现 |
| external CLI registry | 汇总用户机器上的多个命令 | 仅在用户本来就使用 OpenCLI 时可选注册；不是依赖 |
| Browser Bridge / daemon / session lease | 解决浏览器有状态、DOM 漂移和登录态 | 不适用 |
| adapters/plugins | 解决大量异构网站命令 | 不适用；Agent Listening 只有一个深模块 |
| table/CSV/YAML/Markdown 多格式输出 | 面向不同人工读取场景 | 不采用；JSON receipt 是机器 contract，artifact 已有领域格式 |

OpenCLI 的 Agent Skill 明确要求调用者读取 compact state，并在需要时再取详细 payload；结构化错误以 code 分支，不依赖 message string。这和 Agent Listening 的 artifact-first 设计一致。[OpenCLI browser Skill](https://github.com/jackwener/OpenCLI/blob/main/skills/opencli-browser/SKILL.md)

因此，采用 OpenCLI 作为 Agent Listening 的正式入口会形成：

```text
Agent → OpenCLI → external wrapper → agent-listening → extractors
```

这一层没有增加音频能力、schema 能力或远程能力，只增加 Node/runtime、registry 状态和额外故障面。第一性原理上应删除这层。

## 3. JSON、JSON Lines 与大 artifact

### 当前单文件分析：继续使用一个 JSON receipt

一次 `analyze` 只有一个最终事务结果，所以 stdout 最合适的是一个 JSON document：成功或错误各一个 receipt。这样 shell 可以一次捕获，Agent 可以一次解析，extractor 日志不会污染机器通道。

### JSON Lines 只在出现真实流式语义时加入

JSON Lines 要求 UTF-8、每行一个完整 JSON value、以换行分隔；它适合逐 record 处理、shell pipeline、日志和 cooperating processes。[JSON Lines specification](https://jsonlines.org/)

只有以下任一需求实际出现时，JSONL 才比单一 receipt 更合适：

- 一个 `batch` 命令连续分析多个互相独立的音频文件；
- 调用者需要机器可读的长任务 progress/event stream；
- 一个长期 worker 连续接收和返回多个 job。

当前没有这些正式接口，因此不新增 `--jsonl`。如果未来加入，最终 result event 仍应指向 artifact，而不是把 frame arrays 流到 Agent 上下文。

## 4. Agent Skill：发现策略，不是执行引擎

Agent Skills 规范规定，Skill 至少是一个含 `SKILL.md` 的目录；所有 Skill 的 name/description metadata 在启动时加载，完整 instructions 只在激活后加载，references/assets 再按需加载。这正是减少每个 Agent 上下文负担的机制。[Agent Skills specification](https://agentskills.io/specification)

Agent Listening 的薄 Skill 应继续只负责：

- 什么时候使用；
- 如何选择 `solo` / `stem` / `full_mix`；
- 如何找到并运行 CLI；
- 如何先读 receipt，再按 capability 打开 artifact；
- 哪些机器结果尚未经过人工听觉确认。

它不应复制 README、schema、extractor 文档或 raw arrays。规范建议 `SKILL.md` 保持紧凑，并把详细资料放到按需加载的 references；当前 Skill 足够短，不需要再拆文件。[Agent Skills progressive disclosure](https://agentskills.io/specification#progressive-disclosure)

### 更容易安装 Skill 的现成方案

GitHub CLI 现已以 **preview** 形式提供 `gh skill install`，可从 GitHub repo 或本地目录安装 Skill，支持 project/user scope、多种 Agent host、精确路径和 tag/commit pin。对 GitHub 上的 Agent Listening，它比要求用户手工建立 symlink 更容易传播，也不要求项目建立 MCP；但在 GitHub 将该命令标记为稳定前，README 仍应保留手工 symlink 作为稳定 fallback。[GitHub CLI: `gh skill install`](https://cli.github.com/manual/gh_skill_install)；[GitHub CLI: `gh skill` preview status](https://cli.github.com/manual/gh_skill)

当前 Skill 位于隐藏目录 `.agents/skills/agent-listening`；GitHub CLI 对隐藏目录要求 `--allow-hidden-dirs`。在真实 release tag 存在后，可以验证并文档化类似：

```bash
gh skill install OWNER/REPO \
  .agents/skills/agent-listening/SKILL.md \
  --allow-hidden-dirs \
  --agent codex \
  --scope user \
  --pin v0.2.0
```

项目级安装时把 `--scope user` 改为 `--scope project`。在跨 Codex、Claude Code、Cursor 等目标验证完成前，不应为了追求更短命令复制第二份 Skill。

`npx skills add` 也是可用的跨 Agent installer，但它引入 Node/npx；其官方文档也说明默认收集匿名 telemetry，可用环境变量关闭。对于一个已经托管在 GitHub、且用户已有 `gh` 的项目，`gh skill install` 是更短的依赖链。[Skills CLI documentation](https://www.skills.sh/docs/cli)

## 5. CLI 安装和 PATH 发现

### 实施前基线

在本轮实施前，仓库 `pyproject.toml` 把项目标为 `package = false`，没有
`[project.scripts]` console entry point；正式命令依赖 checkout 内的
`bin/agent-listening` wrapper 或手工 PATH symlink。因此，当时不能诚实地把
`uvx agent-listening-cli`、`uv tool install agent-listening-cli` 或
`pipx install agent-listening-cli` 写成发布用法。当前状态见第 11 节。

### 推荐顺序

#### A. 首选：可安装 Python tool + `uv tool install`

Python Packaging 的 `console_scripts` entry point 会让 installer 为一个 Python function 创建系统命令 wrapper；`[project.scripts]` 是标准声明方式。[PyPA entry points specification](https://packaging.python.org/en/latest/specifications/entry-points/)；[PyPA CLI packaging guide](https://packaging.python.org/en/latest/guides/creating-command-line-tools/)

Agent Listening 应先成为正常可构建的 wheel，并声明：

```toml
[project.scripts]
agent-listening = "<import-package>.cli:main"
```

完成真实 wheel 安装测试后，常用机器的推荐安装面是：

```bash
uv tool install "agent-listening-cli==<release>"
agent-listening --version
agent-listening doctor --json
```

`uv tool install` 为每个 tool 建立隔离且持久的环境，并把 executable 放入 PATH；`uvx`/`uv tool run` 则使用隔离的临时环境。uv 也支持从 Git URL、tag 或 commit 运行和安装。[uv tool guide](https://docs.astral.sh/uv/guides/tools/)；[uv tool concepts](https://docs.astral.sh/uv/concepts/tools/)

发布到 PyPI 之前，可在 packageable 之后用 Git tag 做受控安装：

```bash
uv tool install "git+https://github.com/OWNER/REPO@v0.2.0"
```

一次性试用或 CI smoke 才用：

```bash
uvx --from "git+https://github.com/OWNER/REPO@v0.2.0" agent-listening --help
```

Agent Listening 有大型 scientific dependencies 和模型初始化/下载成本，日常使用更适合持久 `uv tool install`，不应把 `uvx` 宣传成每次分析的默认入口。

#### B. 兼容方案：pipx

`pipx install` 同样为应用创建隔离环境并把 console scripts 暴露到 PATH；`pipx run` 适合不永久安装的一次性调用。它是没有 uv 的用户的合理 fallback，而不是需要同时维护的第二套产品架构。[pipx installing applications](https://pipx.pypa.io/latest/tutorial/install-applications.html)；[pipx running applications](https://pipx.pypa.io/latest/tutorial/run-applications.html)

#### C. 暂不做 standalone binary

PyInstaller 能把 Python 和依赖捆成 one-folder/one-file executable，但官方文档建议先让 one-folder 正确工作，因为 one-file 更难诊断；one-file 运行还会把内容解压到临时目录。[PyInstaller documentation](https://pyinstaller.org/en/stable/operating-mode.html)

Agent Listening 包含 Essentia、PyTorch/model tooling、Demucs、Basic Pitch 和平台相关 wheels。standalone 会把当前由 Python packaging 解决的平台矩阵、native libraries、模型缓存和 license notices 转化为项目自己的 release engineering 责任。除非真实用户数据证明“安装 Python/uv”是主要 adoption blocker，否则不做。

## 6. `doctor` 是最值得借的 OpenCLI 能力

对 Agent Listening，首次运行最容易失败的不是命令语法，而是 Python 版本、native/model dependency、profile/schema 文件、模型缓存/下载和输出目录权限。一次 full-mix 分析才发现这些问题，代价太高。

决策是增加一个只做预检、不下载模型、不分析音频的轻量接口：

```bash
agent-listening doctor --analysis-mode solo --json
agent-listening doctor --analysis-mode full_mix --json
```

最小检查集合：

- Agent Listening version 和 receipt/schema versions；
- Python/platform；
- 当前 mode 必需 dependency 的 import 和实际版本；
- profile/schema resource 可读；
- 临时输出目录可创建和原子替换；
- 模型是否已缓存；未缓存只报告 `download_required`，不在 doctor 中下载；
- `full_mix` 才检查 Demucs/all-in-one，`solo`/`stem` 不检查不适用组件。

输出仍是单个 versioned JSON envelope，失败项使用稳定 code，不要求 Agent 解析自然语言。OpenCLI 也把 `doctor` 作为 Browser Bridge setup 后的正式验证步骤。[OpenCLI Quick Start](https://github.com/jackwener/OpenCLI#quick-start)

另外应提供标准 `agent-listening --version`。这两个命令比增加命令 registry、交互式安装 wizard 或 MCP 更直接地降低接入失败率。

## 7. MCP 何时才必要

MCP 定义 host、client、server 之间的 JSON-RPC 通信，并包含 stateful connections、capability negotiation、resources/prompts/tools、progress、cancellation、logging 和安全授权责任。[Model Context Protocol specification](https://modelcontextprotocol.io/specification/)

Agent Listening 当前是本地、单调用、文件输入、artifact 输出。Skill 可以直接执行 CLI，CLI receipt 已携带所有后续路径。此时 MCP 会重复包装同一个函数，并引入 server lifecycle、配置、权限和另一套错误面。

只有出现以下经过验证的 transport/session 需求，才重新评估 MCP：

- 分析运行在另一台机器或集中 GPU worker；
- 多租户并发、queue、job identity、access control；
- 长任务需要跨 Agent session 的 progress、cancellation、resume；
- host 不能启动本地进程，只允许 MCP tool；
- 多轮交互要反复查询由常驻服务持有的状态。

即使未来增加 MCP，CLI 和 artifact schema 仍应是底层 authority；MCP 只做 transport adapter。

## 8. 建议的最小实施路线

| 顺序 | 做什么 | 为什么 |
|---|---|---|
| P0 | 保持现有 `analyze ... --json`、receipt-first 和薄 Skill | 核心调用 contract 已正确 |
| P1 | 把项目变成可构建 wheel，声明 `agent-listening` console script，做 clean-machine wheel smoke | 消除 checkout path 和手工 symlink 依赖 |
| P2 | 增加 `--version` 与最小 `doctor --analysis-mode ... --json` | 最低成本降低首次运行失败 |
| P3 | release tag 后验证 `uv tool install`、Git URL pin、PyPI 安装；pipx 作为 fallback | 让命令从任何项目 PATH 可发现且依赖隔离 |
| P4 | 验证 `gh skill install` 的 user/project scope 和 pin，用 README 给出一条正式命令 | 让 Agent 自动发现，无需复制仓库 |
| 暂缓 | JSONL/batch、standalone binary、Homebrew formula | 有真实 batch/安装数据再做 |
| 不做 | OpenCLI dependency、Browser Bridge、daemon、插件中心、MCP server | 当前不增加产品能力 |

最终用户路径应收敛为两条独立、可组合的安装动作：

```bash
# 一次安装执行能力，所有项目共用
uv tool install "agent-listening-cli==<release>"

# 选择 user 或 project scope 安装薄 Skill
gh skill install OWNER/REPO \
  .agents/skills/agent-listening/SKILL.md \
  --allow-hidden-dirs --agent codex --scope user --pin <release>
```

之后任何音频项目只需要提供音频绝对路径和项目自己的 output directory；不复制 Agent Listening 源码，不启动 server，不把 raw evidence 预载入 Agent 上下文。

## 9. 证据、推断与未验证项

### 实施前已验证事实

- OpenCLI 的正式范围包含 website/browser/Electron/external CLI hub、Browser Bridge 和 daemon。
- OpenCLI 暴露 `doctor`、structured envelopes、compact-first reading 和 external CLI registration。
- Agent Skills 规范原生支持 progressive disclosure。
- uv tool、pipx 和 Python console scripts 已提供 CLI 的隔离安装与 PATH 发现机制。
- MCP 的协议成本包含 stateful connection、capability negotiation、server lifecycle 和安全责任。
- 当时的 Agent Listening repo 是 `package = false`，执行入口是 checkout wrapper；尚不能作为已发布 tool 使用 uvx/pipx。

### 基于证据的产品推断

- OpenCLI 作为 Agent Listening 正式依赖没有净能力收益。
- `uv tool install` + thin Skill 比 wrapper symlink + 每项目复制更容易传播，也比 MCP 更轻。
- `doctor` 和 `--version` 的 adoption 回报高于新增输出格式、registry 或 GUI。
- standalone binary 的收益目前不足以覆盖 scientific/native/model dependency 的发行成本。

### 实施前尚未执行的证据

- 尚未把 Agent Listening 构建成 wheel，也未做 clean-machine installation test。
- 尚未从 Git tag、PyPI、`uv tool install` 或 `pipx install` 安装 Agent Listening。
- 尚未用 `gh skill install` 对当前隐藏 Skill 路径进行 Codex/Claude/Cursor 跨 host 验证。
- 尚未实现或运行 `doctor`。
- 尚无用户安装漏斗、失败率或“缺 Python/uv”导致流失的数据。

因此上述部分是一份 implementation decision brief，不是对实施前发布路径已经可用的声明。

## 10. CLI-Anything 深入审查：有效方法论与过度承诺并存

审查对象是 [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) 当前公开的 README、核心生成指令、HARNESS 方法论、验证与测试命令、Audacity 案例源码，以及项目论文。结论不是简单的“好”或“坏”：

> **CLI-Anything 是一套有价值的 CLI 逆向设计方法和 LLM 脚手架，同时带有明显超过现有证据的通用性与完整性宣传。**

它最有效的场景，是目标软件已经具有稳定的 headless backend、原生文件格式、命令行工具、渲染器或可调用 API，生成 Agent 能把这些真实能力组合成一个结构化入口。它最容易失真的场景，是目标软件的核心能力依赖 GUI 内部状态、交互式视觉判断、闭源组件，或没有真正可调用的后端；此时“为软件生成 CLI”很容易退化为“重新实现一小部分相似功能”。

### 10.1 它实际上是什么

CLI-Anything 不是从 GUI 二进制自动、确定性地编译出等价 CLI 的工具。核心 [`/cli-anything` command](https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/commands/cli-anything.md) 是一份详细的 coding-agent 指令：让前沿模型阅读目标源码和 `HARNESS.md`，分析架构，设计命令，编写 Python、测试、文档、Skill 和安装配置，再迭代到测试通过。

其正式七阶段流程是：

1. 分析目标仓库与真实后端；
2. 设计 CLI 接口；
3. 实现 harness；
4. 制定测试计划；
5. 编写并运行测试；
6. 编写文档和 Agent Skill；
7. 安装到 PATH 并发布。

这是一套可复用的软件工程工作流，不是能力等价性的自动证明。README 也承认它依赖 frontier-class coding model、目标源码和迭代 refinement；benchmark-style 的 agent task-completion suite 仍属于 roadmap。[项目 README](https://github.com/HKUDS/CLI-Anything#limitations)

### 10.2 源码架构和生成模板中真正有效的部分

中央 [`HARNESS.md`](https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/HARNESS.md) 的强项不是某个框架，而是几条合理的接口纪律：

- 先做 interface archaeology：识别真实 backend、GUI 到 API 的调用关系、原生数据模型和已有 CLI；
- 优先调用真实软件，不用 mock 或薄弱替代品冒充生产能力；
- 显式暴露 inspect/list/status，让 Agent 在行动前读取状态；
- 提供结构化 JSON，而不是让 Agent 解析给人看的终端文本；
- 对生成文件做程序化验证，不把 exit code 0 当成内容正确；
- 把验证分为 unit、native/backend integration、CLI subprocess 和真实端到端层；
- 用已安装的正式命令做 subprocess smoke，避免只在源码目录内“碰巧能运行”；
- 在轨迹中只返回紧凑摘要，把大型输出留在文件中按需读取。

这些原则与 Agent Listening 的方向一致，但后者已经有更清楚的领域边界：真实 MIR extractors 产生 observation/evidence，Music IR 承载紧凑 inference，JAMS/raw 保存时间证据，receipt 提供 progressive disclosure，自动结果与人工听觉确认分离。

CLI-Anything 的通用生成模板同时也很重。它通常预设 Click、one-shot 加 stateful REPL、JSON project/session、undo/redo、preview/live/history、固定目录、`setup.py` 和 PEP 420 namespace。这些是“创作型桌面软件控制器”的一种模板，不是所有 CLI 的第一性原理要求。对无编辑状态、单次分析、artifact 输出的 Agent Listening，照搬这些结构会制造第二套 session/project authority。

### 10.3 测试与验证到底证明了什么

[`/validate`](https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/commands/validate.md) 主要验证生成 harness 是否符合 CLI-Anything 自己的结构约定：目录和文件、Click command groups、`--json`、`--project`、错误装饰器、REPL、session、export、测试文件、安装配置、type hints 和 PEP 8。它能有效发现模板缺件，但不能证明：

- CLI 与原软件行为等价；
- “完整能力”已覆盖；
- 输出在领域语义上正确；
- 当前上游版本和当前平台仍可运行。

[`/test`](https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/commands/test.md) 会运行 pytest、检查已安装命令，并把结果写进 `TEST.md`。这是正常且有用的回归流程，但真实 backend 是否被调用、输出是否具备语义正确性，仍取决于每个生成 harness 自己写了什么测试。测试数量和 100% pass 只能证明那些断言通过，不能自然外推成产品的全部能力已经验证。

当前公开 workflows 中，[root Skill consistency](https://github.com/HKUDS/CLI-Anything/blob/main/.github/workflows/check-root-skills.yml)、[Codex Skill installer](https://github.com/HKUDS/CLI-Anything/blob/main/.github/workflows/check-codex-skill.yml) 和 [PR labeler tests](https://github.com/HKUDS/CLI-Anything/blob/main/.github/workflows/pr-labeler-tests.yml) 都不是全 harness 测试矩阵。一个仍开放的 [CI drift issue #403](https://github.com/HKUDS/CLI-Anything/issues/403) 记录了第三方复测：部分 harness 仍 clean，另一些因依赖或行为漂移而失败。该 issue 是用户提交的复现，不应被当成维护者正式结论；但它和 workflow 源码共同说明，README 中的测试计数更接近一次快照，而不是持续、跨平台、对当前 upstream 的 release 证明。

### 10.4 Audacity 案例暴露的能力边界

Audacity harness 是判断“完整 GUI 能力是否真的被 CLI 化”的关键反例。

它的设计文档 [`AUDACITY.md`](https://github.com/HKUDS/CLI-Anything/blob/main/audacity/agent-harness/AUDACITY.md) 正确识别了 Audacity 的 `.aup3` SQLite project，但最终选择了自己的 JSON project format，并用 Python 标准库和 SoX 实现 audio processing。其 [`core/export.py`](https://github.com/HKUDS/CLI-Anything/blob/main/audacity/agent-harness/cli_anything/audacity/core/export.py) 显示：

- WAV mixing/rendering 由 Python 自己执行；
- 部分 effect 是简化算法；
- pitch 与 tempo 可退化为简单速度变换；
- 未知 effects 会被跳过；
- 非 WAV preset 也可能实际写成 WAV。

其 [`test_full_e2e.py`](https://github.com/HKUDS/CLI-Anything/blob/main/audacity/agent-harness/cli_anything/audacity/tests/test_full_e2e.py) 的所谓 true-backend E2E 主要验证 SoX 和生成出来的 Python CLI，而不是启动或驱动 Audacity 本身。

所以这个产物可以是一个有用的轻量 Python/SoX 音频编辑 CLI，但不能据此声称“Audacity 的完整能力已经被 CLI 化”。这也和中央 HARNESS 的“use real software, don't reimplement”原则发生了实质张力：方法论写对了，具体生成物仍可能跨过语义边界。

这正是 Agent Listening 必须避免的错误。Agent Listening 的能力声明应绑定到实际运行的 Essentia、all-in-one、Demucs 和 Basic Pitch、确切版本/模型/参数、输入 hash 和 raw artifacts；不能因为某段自写 DSP 产生了相似字段，就把它包装成对应上游工具或音乐事实。

### 10.5 论文提供了合理理论，但没有证明营销中的普适性

[CLI-Anything 论文](https://arxiv.org/abs/2606.03854) 的核心论点是成立的：Agent 更适合 structured commands、explicit state 和 deterministic feedback；对存在稳定 backend 或 native representation 的软件，可以从已有架构中“lift”出 CLI contract。论文也明确承认 compiled binaries、opaque internal state、visual judgment 和早期 preview coverage 是边界。

但论文的 evaluation 主要统计 interface surface、catalog coverage、demonstrations 和 ecosystem maturity，并没有提供与 GUI automation、MCP 或人工操作的受控任务成功率基准。因此它支持“CLI 是一个很好的 Agent 控制面”这一设计论点，不足以支持 README 中“没有领域限制”“一条命令获得 production-ready comprehensive full capability”等更强主张。

### 10.6 与 Agent Listening 逐项对照

| 维度 | CLI-Anything 通用方案 | Agent Listening 已有 contract | 判断 |
|---|---|---|---|
| 权威入口 | 每个目标软件生成一个 harness | `agent-listening analyze ... --json` | 已足够，不加生成层 |
| 状态模型 | 常见为 project/session/REPL/undo | 输入音频不可变，输出目录承载一次 analysis run | 不引入第二套状态 |
| Agent 接入 | 生成 CLI 后再生成 Skill | 薄 Skill 调稳定 CLI，receipt-first | 现有方案更贴合领域 |
| 结构化输出 | 各命令支持 JSON | 一个 compact receipt 指向 Music IR/JAMS/raw | receipt 更经济 |
| 大输出 | compact trajectory + preview files | raw/frame arrays 留在 JAMS/raw | 原则一致 |
| 真实后端 | 方法论要求真实 backend，但个别 harness 会重实现 | 专用 extractor adapters + provenance | Agent Listening 边界更可审计 |
| 验证 | 模板 conformance + harness 自写 tests | schema、adapter、mode routing、artifact、真实音频、人听边界 | 不用测试数代替能力证明 |
| 分发 | 每个 harness 安装命令，另有 CLI-Hub | wheel/console script + uv tool/pipx + Skill | 标准 Python 分发更小 |
| MCP | 可把外部能力纳入更广生态，但不是核心要求 | 本地进程和文件 artifacts | 当前仍不需要 MCP |
| GUI/preview | 许多 harness 面向编辑器和 preview | 无 GUI，时间戳交给播放器/DAW | 不借 preview/live UI |

### 10.7 值得借的部分

只建议把 CLI-Anything 当成 review checklist，而不是依赖、generator 或新 architecture：

1. **Interface archaeology checklist**：每次新增 extractor 前确认真实 executable/API、原始数据模型、参数、版本、license、artifact 和失败语义。
2. **Installed-command test**：wheel 完成后，从源码目录外用 PATH 中的 `agent-listening` 做 subprocess smoke，防止依赖 checkout 布局。
3. **Backend identity test**：测试不仅确认文件存在，还确认实际 extractor/model 被调用，provenance 与 raw artifact 匹配。
4. **Programmatic artifact verification**：真实音频验收检查 schema、duration/timestamp 范围、hash、MIDI/note consistency 和 compact IR 大小，而不只看 exit 0。
5. **分层测试证据表**：发布报告分别列 unit/schema、native dependency、installed CLI、真实音频、人工听觉复核，禁止相互代替。
6. **Dependency drift CI**：在有可发布版本后，对锁文件和最低支持平台运行真实 harness smoke；这也是从 CLI-Anything 自身 CI 缺口得到的反向经验。
7. **Skill 后置于稳定 contract**：CLI 和 artifact schema 是 authority，Skill 只教调用和渐进读取，不复制领域实现。

### 10.8 明确不该借的部分

1. 不运行 CLI-Anything 生成器来改写当前仓库；现有 purpose-built pipeline 比通用 harness 模板更深、更可审计。
2. 不迁移到 Click，仅为了和其模板一致；当前 CLI surface 很小，没有已证实收益。
3. 不增加 REPL、global session、undo/redo、JSON project、history、preview 或 live mode。
4. 不增加 CLI-Hub 或项目自己的插件 registry；一个命令使用标准 wheel 和 PATH discovery 即可。
5. 不把每个内部动作都暴露成 command，也不要求每个 command 都重复输出 JSON；稳定 receipt 是更小的 Agent contract。
6. 不从命令装饰器自动生成并覆盖 Skill；手写薄 Skill 承载 capability status、证据层级和 human-review 边界，不能退化为 help mirror。
7. 不复制 Audacity/SoX harness 或其中的简化 DSP；它既不产生本项目需要的新音乐证据，也可能模糊真实 extractor 身份。
8. 不采用“测试很多且 100% pass = 全能力生产就绪”的发布语言。
9. 不引入 preview bundle、GUI render 或图形依赖；当前 timestamps、JAMS 和外部播放器/DAW 已满足审听定位。
10. 不因为 CLI-Anything 存在就增加 MCP。Agent Listening 当前没有远程 transport、共享 session、跨主机 job 或 host 进程限制。

### 10.9 最终产品决定

CLI-Anything 不应进入 Agent Listening 的 runtime、development dependency 或代码生成流程。它对本项目的净价值是一张审查清单：**真实后端、显式状态、结构化输出、已安装命令、真实文件验证、紧凑 Agent 轨迹**。

Agent Listening 已经采用了其中最关键的第一性原理，而且通过 extractor provenance、dual artifacts、receipt-first 和 human-review separation 做得更严格。最经济、最有效的下一步仍是上一节的 P1–P4：把现有 CLI 做成可安装、可诊断、可由薄 Skill 自动发现的稳定工具，而不是再套一层通用生成 harness。

### 10.10 本轮证据边界

本轮已阅读公开 README、HARNESS、生成指令、验证/测试命令、Audacity 设计与实现、公开 workflows、开放 CI issue 和论文。没有在本机 clone CLI-Anything，没有运行其生成器，没有安装或执行任何生成 harness，也没有复现 issue #403 的各平台失败。因此：

- “源码架构、生成流程、模板验证范围、Audacity 实现边界”是直接从公开源码验证的事实；
- “两者兼有”“适合作 checklist、不适合作 dependency/generator”是基于这些事实的产品判断；
- 各 harness 当前在所有平台和最新依赖上的通过率，仍是未执行证据；
- 这份结论没有改变 Agent Listening 产品代码、依赖或发布状态。

## 11. 2026-08-30 实施状态更新

本轮按上述 P1–P4 的最小范围落地，并重新运行了本地检查：

- `pyproject.toml` 现在声明 `agent-listening-cli==0.2.0`、MIT、
  `agent-listening` console script，以及 Essentia、Basic Pitch、Demucs 和
  all-in-one 的直接依赖；`uv lock --check` 通过。
- 新增 `agent-listening --version` 和
  `agent-listening doctor --analysis-mode solo|stem|full_mix --json`。doctor
  只检查 Python、依赖 metadata/module discovery、打包资源和输出可写性，
  明确不加载模型、不运行音频推理、不替代人工听审。
- 用 setuptools backend 实际构建了 wheel 和 sdist；从 checkout 外把 wheel
  安装进已有依赖环境后，`agent-listening --version`、solo/full_mix doctor
  以及安装后的 `build-ir --json` fixture smoke 均通过。wheel 中包含
  `profiles/` 和 `schemas/`，不要求当前 checkout 目录存在。
- 本地 unittest 为 75/75 通过，`compileall` 和 31 个 Music IR JSON 的
  schema 校验通过；CI 增加同一套 `uv build` 和 checkout 外安装 smoke。
- README、README.zh-CN、CREDITS、ADR 和 AGENTS.md 已改为说明 GitHub tag
  安装、project/user Skill scope、receipt-first 读取和无 GUI 边界；没有把
  OpenCLI 或 CLI-Anything 变成依赖。

仍未完成或不能由本机证明的事项必须单独标记：

- 当前执行环境的 `uv build` 无法访问 PyPI 的 build isolation，因此本轮用
  已安装 setuptools backend 证明构建逻辑；CI 的联网 `uv build` 尚未在这里
  执行。
- 本地 Git worktree 的 `.git` 元数据和 `.agents/` 被宿主权限设为只读，因而
  本轮不能在这里创建 commit，也不能更新 Skill 文件；现有 Skill 仍是旧的
  checkout-wrapper 文案。README 已给出目标安装方式，但远端 Skill 需要在
  可写 checkout 中同步一次。
- GitHub connector 的写入操作需要当前会话未提供的审批，且本机 `gh` token
  无效；因此本轮没有宣称已 push、合并、打 tag 或创建 GitHub Release。v0.2.0
  是目标版本号，不是已被本轮证明存在的公共 release。
