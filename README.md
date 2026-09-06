# 江导三分身 Skills

版本：V1.0.2。提供 **Codex 版** 与 **豆包版**。

## 自动识别使用环境

- **Codex**：读取根目录 `release-manifest.json`，使用根目录的 Skills 与 `shared/`。
- **豆包**：优先读取 [豆包版清单](doubao/release-manifest.json) 和 [豆包版说明](doubao/README.md)，仅安装 `doubao/` 内的 Skills 与 `shared/`。不要安装根目录的 Codex 版；豆包版缺失或校验失败时停止并说明原因。
- 其他环境：先确认兼容性与技能目录，再决定安装方式。

## 复制给你使用的 AI

把下面这段话发给 Codex 或支持本地工具的豆包：

```text
请读取仓库 https://github.com/CAPTAINJJJF/jiangdao-skills ，根据你当前运行的环境选择对应版本：Codex 使用根目录普通版；豆包优先读取 doubao/release-manifest.json，获取 doubao/ 豆包版。按照对应说明完整安装并核验，保留我的个人资料和配置；缺少工具时说明并协助配置。
```

安装完成后，新开任务，按[用途与启动语目录](shared/skill-entry-guide.md)选择入口。可以输入“启动本我分身”“启动操盘手分身”“启动内容编导分身”，也可以直接输入“启动方向探索”“启动爆款拆解”等专业启动语。无法执行本地工具的环境应说明限制，不声称已经完成安装。

## Codex 安装说明

供 Codex 执行：获取仓库后，在根目录使用 Python 3.10+ 运行：

```bash
python3 verify_dual_bundle.py
python3 install_bundle.py --check
python3 install_bundle.py
```

默认安装到 `${CODEX_HOME:-$HOME/.codex}/skills`，可用 `--dest` 指定实际技能目录。已有同名目录时，安装器会停止；先保留旧安装和个人配置，核对变化后完成切换。15 个 Skills 与 `shared/` 必须完整安装，不能单独拆装。豆包请按 [豆包版说明](doubao/README.md) 操作。

## 按需求选择入口

- 本我分身：认识自己、情绪支持与 Live 深聊接力。
- 操盘手分身：方向、定位、行动与经营判断。
- 内容编导分身：研究、选题、内容生产与复盘。

11 个专业能力可独立启动，继续归属三个分身。全部中文启动语无需加“江导”。发布复盘暂留内容编导内部，不作为独立入口。独立使用无需走完整套分身流程；安装仍保留完整依赖。

[查看全部 14 个入口、启动语与所需材料](shared/skill-entry-guide.md)

## 工具与配置

文字任务可从已有材料开始。数据库编译需要 Node.js；采集、转写、剪辑和发布按具体任务检查所需工具。工具缺失时，先说明缺口并协助安装配置，实际账号登录由使用者完成。运行 `shared/scripts/check-runtime.py --stage <阶段>` 可检查对应条件；不要把尖括号占位符直接作为参数。

本地 ASR 当前使用 Apple Silicon Mac 的 MLX 路线，其他系统需要适用的转写工具。视频工程仍需 ChatCut、剪映及对应扩展能力，按实际环境核验。

参见 [运行配置](shared/runtime-configuration.md) 与 [配置模板](shared/runtime-config.example.json)。个人资料与配置由使用者自行保管。

## 版本记录与许可

[版本记录](CHANGELOG.md) · [发布页](https://github.com/CAPTAINJJJF/jiangdao-skills/releases/latest) · [LICENSE](LICENSE)

使用范围以 LICENSE 为准；第三方文件遵守其附带许可。
