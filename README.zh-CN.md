# Agent Listening CLI

[English](README.md) | 简体中文

Agent Listening CLI 是一个本地、确定性、artifact-first 的音频分析工具。
它把完成的音频转换为供下游 Agent 使用的紧凑 Music IR、带时间轴的 JAMS
证据档案，以及保留下来的原始 extractor 输出。Agent 通常只需要读取小型
JSON，不需要把源代码或逐帧数组塞进上下文。

## 名称约定

下面三个名称是有意分开的：

| 对象 | 稳定名称 | 含义 |
| --- | --- | --- |
| 项目 / lock metadata | `agent-listening-cli` | `pyproject.toml` 和 `uv.lock` 中的项目名；不代表已经发布 PyPI 包。 |
| 可执行命令 | `agent-listening` | 正式支持的 CLI 调用界面。 |
| Agent Skill | `agent-listening` | `.agents/skills/agent-listening/` 下的薄指令目录。 |

因此可以重命名或 symlink checkout 目录而不破坏现有调用。正式集成界面是
CLI；Skill 只是 CLI 的发现和 progressive disclosure 层，不需要配置 MCP
server。

## 产品边界和特点

管线保持小而明确：

- 本地运行，不依赖云服务、账号或本地 Web server；
- 使用确定性的 MIR extractor 生成声学和结构观察；
- 分开保存 raw observation、normalized evidence 和 compact inference；
- 默认 no-clobber，并以原子方式写入 artifacts；
- 先生成机器可读 receipt，再按问题打开更深层的 artifact；
- 所有事件带时间戳，人员可以在外部播放器或 DAW 中试听定位；
- 不把自动生成的音符、调性、段落或 source separation 结果宣称为人工听觉
  真值。

下游 Agent 的普通推理只需要小型 Music IR。完整 frame vectors、pitch
contours、note events 和 extractor payload 仍然保留，只有在确实需要时才
读取。

## Architecture

```text
音频文件
    │
    ▼
bin/agent-listening ── locked uv environment ──► src.cli
                                                     │
                                                     ▼
                                             src.core orchestrator
                                                     │
                 ┌───────────────────────────────────┼────────────────────┐
                 ▼                                   ▼                    ▼
          Essentia adapter                    all-in-one adapter      Demucs adapter
          声学/逐帧/音高证据                    节奏/段落候选           full_mix 分离
                 │                                   │                    │
                 └────────────── 原始 extractor evidence ────────────────┘
                                                     │
                                                     ▼
                                       pure evidence fusion / validation
                                                     │
                       ┌────────────────────────────┼─────────────────────┐
                       ▼                            ▼                     ▼
                 Music IR 0.2                    JAMS                raw/symbol/stem
                       └────────────────────────────┬─────────────────────┘
                                                    ▼
                                                JSON receipt
                                                    │
                                                    ▼
                                     thin Skill → downstream music agent
```

实现分为四层：

| 层 | 内容 | 主要位置 |
| --- | --- | --- |
| Observation | 工具原生的逐帧数组和模型输出 | `src/adapters/`、`raw/` |
| Evidence | 时间网格、provenance、confidence、归一化事件 | `src/fusion/`、JAMS |
| Inference | 紧凑摘要和 capability status | `schemas/`、Music IR |
| Execution | CLI 调用和 Agent handoff | `bin/`、`src/cli.py`、Skill |

关键 seam 是 `src.core.analyze(audio_path, profile, ...)`。Extractor 可以在
这个 seam 后替换；下游调用方不需要依赖 Essentia、Basic Pitch 等工具的
原生 JSON 格式。

## 三种 analysis mode

根据你实际拥有的输入选择 mode：

| Mode | 适用输入 | 会运行 | 不会运行 |
| --- | --- | --- | --- |
| `solo` | 一条 humming、vocal 或单件乐器 render | Essentia 声学/逐帧/material evidence、Essentia 连续音高、Basic Pitch 音符和 MIDI | all-in-one、Demucs |
| `stem` | 调用方已经知道身份的单条 stem | 与 `solo` 相同的声学、音高和音符管线 | all-in-one、Demucs |
| `full_mix` | 含多个声源的完成混音 | full-mix Essentia 和 all-in-one、material events、Demucs `htdemucs_6s`，以及逐 stem 的 activity/pitch/notes | 对 `drums` stem 运行 Basic Pitch |

`solo` 是成本最低、最适合先跑的路径。`full_mix` 成本明显更高：它可能
下载模型，并分析最多六条分离 stem：`vocals`、`drums`、`bass`、`guitar`、
`piano`、`other`。第一次运行 all-in-one、Demucs 或 Basic Pitch 也可能下载
模型权重。模型权重的条款与 Python 包许可证不同，请阅读
[CREDITS.md](CREDITS.md)。

## 在新音频项目中接入

音频项目不需要复制 Agent Listening 源代码。保留一个权威 checkout，只向
项目暴露它需要的 Skill 和/或 CLI wrapper。

### 1. 准备权威 checkout

在本仓库目录执行一次：

```bash
uv sync --locked
```

wrapper 会自行解析本 checkout，即使从其他工作目录调用也可以：

```bash
"/absolute/path/to/Agent Listening/bin/agent-listening" --help
```

### 2. 选择 Skill 的作用范围

一个音频项目使用时，默认采用项目级 Skill：

```bash
REPO="/absolute/path/to/Agent Listening"
AUDIO_PROJECT="/absolute/path/to/my-audio-project"
mkdir -p "$AUDIO_PROJECT/.agents/skills"
test ! -e "$AUDIO_PROJECT/.agents/skills/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/.agents/skills/agent-listening" \
  "$AUDIO_PROJECT/.agents/skills/agent-listening"
```

如果多个本地项目都应发现同一个 checkout 和同一个 Skill 版本，可以使用全局
位置：

```bash
REPO="/absolute/path/to/Agent Listening"
mkdir -p "$HOME/.agents/skills"
test ! -e "$HOME/.agents/skills/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/.agents/skills/agent-listening" \
  "$HOME/.agents/skills/agent-listening"
```

项目级适合需要明确归属和复现的单一项目；全局级只适合有意共享同一个本地
authority 的情况。不要把源代码复制进每个音频项目；复制会造成版本漂移。只有
在项目必须脱离该 checkout 独立携带时，才有理由做真正的 copy。

### 3. 让 CLI 可被调用

Skill 不会替代可执行命令。Agent 或脚本可以直接调用 wrapper，也可以把一个
独立 symlink 放到 `PATH`：

```bash
REPO="/absolute/path/to/Agent Listening"
mkdir -p "$HOME/.local/bin"
test ! -e "$HOME/.local/bin/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/bin/agent-listening" "$HOME/.local/bin/agent-listening"
```

当前支持的是 checkout + `uv` 运行方式，不代表已经发布了 PyPI 包或系统级
binary。

### 4. 把分析输出写入项目自己的目录

生成的 artifacts 应放在音频项目自己的 analysis 目录，不要写进 Agent Listening
源码 checkout：

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/renders/humming.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/my-audio-project/analysis/humming" \
  --json
```

调用方已经提供 stem 时：

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/stems/woodwind.wav" \
  --analysis-mode stem \
  --output-dir "/absolute/path/to/my-audio-project/analysis/woodwind" \
  --json
```

完成混音需要声源分离时才使用 `full_mix`：

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/renders/final-mix.wav" \
  --analysis-mode full_mix \
  --output-dir "/absolute/path/to/my-audio-project/analysis/final-mix" \
  --json
```

项目为了被 Agent 发现，实际只需要增加一个 Skill symlink：

```text
my-audio-project/
└── .agents/
    └── skills/
        └── agent-listening -> /absolute/path/to/Agent Listening/.agents/skills/agent-listening
```

### 5. 让 Agent progressive disclosure 地读取

Skill 不应预先加载源代码或逐帧数组。读取顺序固定为：

1. `--json` 打印的 receipt；
2. `music-ir/<track>.music-ir.json`，用于普通推理；
3. `jams/<track>.analysis.jams`，仅在需要时间戳、候选、曲线或 material events
   时读取；
4. receipt 表明 capability 可用时，才读取 `symbols/` 或 `stems/`；
5. 只有做 provenance audit 或 diagnosis 时才读取 `raw/`。

需要人工确认时，使用事件时间戳在外部播放器或 DAW 中定位。工具保留数字化的
waveform/spectrum evidence，但不渲染 GUI、波形页面或 spectrogram 图片。

## CLI 参考

正式界面是：

```text
agent-listening analyze AUDIO \
  --analysis-mode full_mix|stem|solo \
  --output-dir OUTPUT \
  --json
```

| 选项 | 作用 |
| --- | --- |
| `analyze AUDIO` | 对一条 `.wav` 或 `.flac` 音频运行 native/model-backed analysis。 |
| `--analysis-mode` | 选择 `solo`、`stem` 或 `full_mix`；默认是 `full_mix`。 |
| `--output-dir`、`-o` | 所有 artifacts 的根目录；默认是当前目录。 |
| `--profile`、`-p` | Essentia profile；默认是 `essentia_v0_1`。 |
| `--json` | 向 stdout 打印一个机器可读 receipt；库的进度信息写到 stderr。 |
| `--overwrite` | 明确替换该 track 的既有 artifacts；省略时保持 no-clobber。 |

`build-ir` 是开发者使用的离线编译器，用于已经捕获的 extractor JSON，不是
普通 Agent 的调用界面：

```bash
uv run --locked python -m src.cli build-ir \
  --allin1 tests/fixtures/allin1_sample.json \
  --essentia tests/fixtures/essentia_sample.json \
  --track-id example \
  --output-dir /tmp/agent-listening-output \
  --json
```

带 `--json` 的错误会以非零退出，并将 error receipt 写入 stderr。不要因为输出
目录中有部分文件就把它当作成功分析。

## Artifact contract

一次成功运行会在指定 output directory 下原子写入：

```text
output/
├── music-ir/<track>.music-ir.json       # 紧凑 Music IR 0.2
├── jams/<track>.analysis.jams            # 带时间轴的 evidence
├── raw/<track>/
│   ├── essentia.json
│   ├── allin1.json                       # 仅 full_mix
│   ├── demucs-manifest.json              # 仅 full_mix
│   ├── pitch.json                        # solo/stem，pitch 成功时
│   ├── stems/<source>.essentia.json      # full_mix，有效时
│   └── basic-pitch/<source>.notes.json   # note extraction 成功时
├── stems/<track>/*.wav                   # full_mix，仅写入存在的 stems
└── symbols/<track>/
    ├── <source>.notes.json               # 完整 note evidence
    └── <source>.mid                      # 生成时才有 MIDI
```

Extractor 失败或没有检测到内容时，optional artifact 不会创建空文件。Receipt
包含绝对路径、capability status、机器验证结果和相同的读取顺序。

紧凑 IR 保存 loudness、spectral descriptors、energy bands、tempo candidates、
tuning/key evidence、pitch range、note density、source summaries 和
material-change candidates 等摘要。完整 frame arrays 留在 JAMS/raw，不进入每个
下游 Agent 的默认上下文。

必须遵守的证据规则：

- section acoustic summary 必须使用合法的局部时间网格；没有网格时字段为
  `null`，不能拿全曲值复制冒充局部值；
- material events 是带前后窗口的 machine candidates，不是人工标签；
- 自动 note events 是 machine transcription，不是 score ground truth；
- Basic Pitch amplitude/velocity 不是 loudness；
- 弱的 key、beat 或 section 候选可以保留在 raw evidence 中，但不能升级成确定
  事实；
- `review.human_checked` 在有人试听前必须保持 pending/false。

## 验证

### 代码或依赖改动后的 checkout 验证

```bash
uv sync --locked
uv run --locked python -m unittest discover -v
uv run --locked python -m compileall -q src tests
bin/agent-listening --help
bin/agent-listening analyze --help
git diff --check
```

测试覆盖 adapter parsing、原生 timestamp grids、局部 section aggregation、
material-event timing、mode routing、Basic Pitch preservation、Demucs manifest、
schema compatibility、receipt/no-clobber 以及 atomic artifact。Music IR 使用
Draft 2020-12 JSON Schema，JAMS 使用官方 base schema。如果 extractor 没有为每条
observation 提供数字 confidence，不宣称 namespace-strict confidence validation
已经通过。

同时检查两版 Schema 和历史 demo artifact：

```bash
uv run --locked python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

for schema_path in Path("schemas").glob("music-ir-v*.schema.json"):
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)

demo = json.loads(Path("music-ir/demo-track-001.music-ir.json").read_text())
version = demo["schema_version"].rsplit("/", 1)[-1]
schema = json.loads(Path(f"schemas/music-ir-v{version}.schema.json").read_text())
Draft202012Validator(schema).validate(demo)
print(f"schema checks passed ({demo['schema_version']})")
PY
```

### 一次真实分析的验证方式

先捕获 receipt，不要先打开深层文件：

```bash
RECEIPT="$(agent-listening analyze \
  "/absolute/path/to/audio.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/analysis/audio" \
  --json)"
printf '%s\n' "$RECEIPT"
```

确认 `status == "success"`，解析 `artifacts` 中的绝对路径，并确认：

```text
validation.music_ir == "passed"
validation.jams_base_schema == "passed"
```

然后读取 compact Music IR。只有问题确实需要时，才打开 JAMS 或 raw。成功
receipt 只证明 extraction、持久化和机器 Schema 验证完成，不证明感知正确性。

运行 `full_mix` 时，还要检查 receipt 的 capability status 和 Demucs manifest，
再使用任何 stem 结论。失败的 optional extractor 必须明确保持 `failed` 或
`not_detected`，不能擦除成功的 full-mix 声学 evidence。

## Credits、许可证和发布状态

项目自己的代码使用 MIT License，见 [LICENSE](LICENSE)。运行依赖和设计参考各自
保留原许可证，并在 [CREDITS.md](CREDITS.md) 中按名称、版本、作用和链接列出。
Essentia 是 AGPL-licensed；all-in-one、Demucs 和 Basic Pitch 的模型权重也有
独立于 Python 包代码的发布条款。仓库不复制上游源代码。

影响当前边界的参考项目与运行依赖分开记录：soundscape-analyse 提供
material-change review 思路，Ocean Listen 提供 separation-first/per-stem 思路，
Mu2Mi 提供 compact representation 的产品比较；audioFlux 和 music21 已评估但
没有加入。列出名称和链接不代表复制了它们的代码。

MIT 文件只说明本项目代码的许可证，不意味着模型、输入录音或 transitive
package 可以按 MIT 再分发。当前 checkout 已完成本地技术实现和测试，但没有因为
存在 LICENSE 就自动形成公开 release、PyPI 发布或可再分发模型包。

## 明确不做的事情

本版本不包含 GUI、桌面应用、Web app、本地 Web server、MCP server、交互式
waveform/spectrogram 页面，也不默认生成 PNG/SVG/HTML/PDF 报告。不加入
Streamlit、React、Next.js、Plotly、Altair、Matplotlib、PANNs、Parselmouth、
Whisper、FunASR、audioFlux、music21、MOSS 或独立的 audio language model。
`all-in-one-infer` 当前会传递加载 Matplotlib，但本项目不直接调用它的绘图
helper。

Waveform 和 spectrum 数值仍然作为证据保留。只有当出现真实的人类审听工作流
需求时，才考虑单独设计 render 命令；当前版本不会预留空的 GUI 或绘图接口。
