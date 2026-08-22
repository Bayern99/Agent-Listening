# Audio-to-Music-IR 低代码选型研究记录

## 用户目标与约束

- 目标：将用户已制作的成品音乐导入系统，转为可读取、可检索、可供后续音乐智能体或 SuperCollider 使用的数字化、结构化信息。
- 不以科研、训练新模型或大规模工程为目标；优先采用开源仓库的组合，避免从头编写大型代码项目。
- 既有研究方向：Music IR 作为音频感知输出与后续推理/合成之间的中间表示；JAMS 承载带时间的可复核音乐注释，扩展 JSON 承载音色、层次、制作和执行提示。

## 既有研究的关键更新

- 对复杂真实多乐器录音，MuScriptor 是候选的多乐器符号转录器；其 MIDI 是观测结果而非真值，需与节拍、和声等专门模块交叉验证。
- 音频语言模型应只担任自然语言描述、问答和假设生成的弱证据，不应单独决定精确节奏、和声或结构事实。
- JAMS 适合保存原始时序注释和多种候选，Music IR 扩展适合保存角色、音色意图、置信度与后续实现提示。

## 本轮已核验：allin1

官方仓库：<https://github.com/mir-aidj/all-in-one>，访问日期：2026-08-22。

- allin1 是 MIT 许可的音乐结构分析器，预训练模型可直接输出 BPM、beat、downbeat、功能段落边界及 intro / verse / chorus / bridge / outro 等段落标签。
- 命令行分析会输出 JSON，字段涵盖 bpm、beats、downbeats 和带 start、end、label 的 segments；也提供 Python `analyze()` 接口。
- 可选导出可视化、sonification、frame-level activation / embedding 与 demix 相关文件；基础依赖为 PyTorch，MP3 支持时可选 FFmpeg。
- 初步判断：这是 V0.1 中最匹配“少写代码、直接产生结构 JSON”的结构层工具，优先级高于需要自行搭建长音频服务的大模型。其角色仅限结构与节拍证据，不输出乐器、和弦、音色和成品语义描述。

## 本轮已核验：MOSS-Music

官方仓库：<https://github.com/OpenMOSS/MOSS-Music>，访问日期：2026-08-22。

- MOSS-Music 在音乐描述、歌词 ASR、调性/节拍/和弦推理、结构分析、乐器与人声识别、长曲问答方面提供统一生成式接口；公开两个约 9.1B 规模的 8B 变体。
- 它使用音频编码器、适配器和语言模型，音频的时序表示为 12.5Hz；通过跨层特征注入保留低层瞬态、节奏和音色信息，并使用时间标记支持带时间戳的结果。
- 仓库提供本地 Transformers 推理、服务和 Gradio 应用路径，但体量与运行依赖都显著大于 V0.1 的需求；README 对若干评测的主张仍属项目方报告，不能替代交叉核验。
- 初步判断：作为“听感语言化”和交互问答的可选增强模块有价值，但不应是第一版必选依赖，也不应作为任何可执行音乐事实的唯一来源。

## 后续待核验的独立输入流

1. Essentia 的预构建命令行 / streaming-extractor 是否能直接成为低代码声学、调性、节奏、乐器特征输出层，以及 AGPL-3.0 对用户实际使用方式的影响。
2. Sonic Annotator + Vamp（含 Chordino、QM 等）是否能通过单一命令批量导出 CSV/RDF，作为可脚本化但不需编程的和弦与描述符路径。
3. JAMS / jams-python 的验证及其与 JSON 扩展共存的实际办法。
4. MuScriptor 或 Basic Pitch 的安装、推理成本及产物可用性；其中 Basic Pitch 可能是更轻量的可选 MIDI 通道。
5. n8n / Node-RED 等可视化编排器能否作为“上传音频 → 调用命令 → 合并 JSON → 归档”的无代码入口，且不将其误认为 MIR 本身。

## 本轮已核验：Essentia

官方仓库：<https://github.com/MTG/essentia>；提取器文档：<https://essentia.upf.edu/streaming_extractor_music.html>，访问日期：2026-08-22。

Essentia 的 `essentia_streaming_extractor_music` 是可配置命令行工具，专为“不写程序就批量提取常用音乐描述符”设计，能够输出 JSON 或 YAML。它可产生声学、节奏、调性和可选高层分类器输出，包括 EBU R128 loudness、动态复杂度、谱质心/rolloff/flux/MFCC、BPM/beat位置/onset rate、三种 profile 的调性与强度、和弦统计等；可通过 YAML profile 规定分析时段、帧参数、聚合方式及是否输出逐帧值。

这使其成为 V0.1 最重要的“可复核数值证据层”：它不会直接给出“电影感、黑暗、温暖”等可靠主观语义，却能给后续分析、对比和合成映射提供节奏、调性、动态和频谱基础。官方说明也提醒不同 Essentia 版本的描述符和高层模型可能不兼容，故每条输出必须保留 Essentia 版本与 profile 哈希。代码为 AGPL-3.0；如将其嵌入或托管在面向他人提供服务的闭源产品中，必须在实施前另行审查合规性。个人本地使用或自身开源仓库并不改变其对低代码使用的价值。

## 本轮已核验：Sonic Annotator + Vamp

官方页面：<https://vamp-plugins.org/sonic-annotator/>，访问日期：2026-08-22。

Sonic Annotator 是批量调用已安装 Vamp 插件的命令行标注工具，能从本地音频或 HTTP/FTP URL 读取音频，并将结果写为 RDF 或 CSV。它适合需要把某个插件的输出原样归档的场景，例如以 Vamp 音乐分析插件得到和弦、节拍或描述符。但它的输出更像研究交换数据，而不是可以直接交给音乐智能体的统一 JSON；它与插件本身均需要逐项验证。其 GPL 许可也会影响未来发布方式。

初步判断：Sonic Annotator 是可选的“插件生态逃生口”，不应作为 V0.1 主干。若 Essentia 的 JSON 以及 allin1 的 JSON 已覆盖目标，先不要把它加进系统；只有需要特定 Vamp 算法时才加入。

## 本轮已核验：JAMS 与 Basic Pitch

官方文档：<https://jams.readthedocs.io/en/stable/>；Basic Pitch 仓库：<https://github.com/spotify/basic-pitch>，访问日期：2026-08-22。

JAMS 有正式 JSON schema，可在一个音频文件中容纳多个 annotation，并定义 beat、chord、key、segment、tempo、tag 等 namespace，同时提供验证和与 mir_eval 的转换接口。实际使用上，建议每首曲保存原始 `analysis.jams`（事实与证据）以及派生 `music-ir.json`（面向使用的凝练结果）两个文件，而不要令后者替代前者。

Basic Pitch 为 Apache-2.0 许可的轻量自动转录器，支持单条 CLI 批量输入并生成 MIDI；可选输出 note-events CSV 和 MIDI sonification。它支持多音和多类乐器，却在官方说明中明确“单一乐器时最佳”；输入会下混到单声道并重采样到 22.05 kHz。因此，对成品混音而言应把它设为可开关的“旋律/骨架候选”通道，而不是将其输出当作整曲多音轨乐谱。若用户只需要音乐的结构、节拍、调性、能量和音色特征，第一版可不启用它。

## 本轮已核验：MOSS-Music-Data-Pipeline

官方仓库：<https://github.com/wx9Songs/MOSS-Music-Data-Pipeline>，访问日期：2026-08-22。

该仓库确实实现“原始音乐到结构化训练样本”的完整流水线：时长扫描后并行运行 ALM 描述、基于 Chordino + BeatNet + Essentia 的 MusicToolsPipeline、SongFormer 结构分析；随后分段、歌词 ASR、段级调性分析、元数据合并，最后生成对话式训练数据。其设计说明和输出 JSONL 结构很有借鉴意义。

但它的定位是批量构建音乐理解语料，并非单曲/小曲库的轻量工具。其快速开始会下载约 8GB 权重，局部模式要求通过 Ray 运行 CPU/GPU 模块，SongFormer 使用本地 GPU，并预期另行部署音频语言模型、歌词 ASR 与最终 LLM 的 OpenAI 兼容端点。因此，它应作为“看架构、借字段、日后扩展”的参考仓库，而不是用户此刻的基础仓库或 V0.1 依赖。

## 本轮已核验：n8n 的编排边界

官方文档：<https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/>；<https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.readwritefile/>，访问日期：2026-08-22。

n8n 的自托管实例可以读取/写入本机可访问目录，也可以通过 Execute Command 节点调用宿主机或容器内的命令，因此理论上可提供一个可视化的“上传音频→运行 allin1/Essentia/Basic Pitch→收集 JSON→归档”的界面。重要限制是 Execute Command 自 n8n 2.0 起默认禁用，且官方明确警示其安全风险；在 Docker 环境下命令和文件均发生在容器内部，必须挂载音频目录与工具二进制/环境。

因此不建议用 n8n 启动项目：它会把三个成熟 CLI 的简单顺序任务变成服务器、容器、权限与安全配置问题。只有当用户需要持续处理多个文件夹、定时处理或上传界面时，再以仅处理受信任音频、受限目录、允许列表命令的方式加上 n8n。对于单机单人 V0.1，一个明确的 `run_analysis.sh` 或双击启动器更低代码、更易复现。

## 当前可比方案（待完成评估）

| 路线 | 核心组件 | 适合程度 | 初步结论 |
|---|---|---:|---|
| 最小可用结构化底座 | allin1 + Essentia + JAMS/Music IR | 很高 | 推荐作为 V0.1 主线；核心输出均是 JSON，且无需 GPU 才能起步。|
| 加符号骨架 | 主线 + Basic Pitch | 高（需旋律/音符时） | 可选，不适合把混音直接转成完整真实乐谱。|
| 大型语料/强语义 | MOSS-Music-Data-Pipeline + 独立服务 | 低（当前阶段） | 不作为基础仓库，作为架构参考与后期升级路径。|
| GUI/自动化前端 | 主线 + n8n | 中（将来） | 等核心命令行流程稳定后再添加，避免先上复杂运维。|
| 专门插件工具箱 | Sonic Annotator + Vamp | 中低 | 仅在已有组件没有所需算法时按需加入。|

