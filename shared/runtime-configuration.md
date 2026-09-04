# 使用者配置与可选运行环境

Skill 包只保存通用规则。身份与人格库位置、工具目录和服务配置由使用者维护，不随包分发。

## 配置读取

可设置 `JIANGDAO_RUNTIME_CONFIG` 指向 JSON 文件；未设置时依次读取当前工作项目的 `config/jiangdao-runtime.json`、使用者的 `~/.config/jiangdao/runtime.json`。优先使用第一个存在的文件，不混合多个身份配置。相对路径相对配置文件所在目录解析。空值表示尚未配置；不搜索其他人的目录自动填充。格式见 [配置模板](runtime-config.example.json)。

`identity_owner` 与 `personality_database` 仅提供候选归属和路径。先按本我规则识别当前服务对象，确认材料属于该身份后才使用；演示、学员、第三方或不明确身份不得据此写入。配置本身不能证明当前说话人是谁。

未配置人格库时优先使用当前工作空间中归属明确的记录；新老学员不按“有没有配置文件”判断。缺少跨项目持久化真源时暂缓跨项目写入，正常对话与 Live 交接继续。

## 可选环境

在当前工作项目目录调用包内 `shared/scripts/check-runtime.py --stage <阶段>`。此检查只读，不安装、不登录、不读取 Cookie；通过只表示初步环境可用。

| 阶段 | 要求与配置 | 未满足时 |
|---|---|---|
| core | Python 3.10+、Node.js；共享规则完整 | 提示缺失命令，不宣称相关校验已执行 |
| douyin | `douyin_downloader` 或 `JIANGDAO_DOUYIN_DOWNLOADER` 指向已安装下载器；固定已验收版本与隔离环境 | 停在采集依赖缺失，不阻止已有文本的研究生产 |
| transcribe | Apple Silicon Mac、uv、ffmpeg/ffprobe、Node；首次运行下载 MLX Whisper 模型 | 可接收已有可信逐字稿，不静默使用收费云服务 |
| edit | 外部 `course-cut-review`；选定路线所需工具、ChatCut/剪映和真实小样 | 保留原片与既有成果，说明当前缺少的执行能力 |
| full-package | edit 条件＋`motion_style_library`，目录须含固定风格目录、选择页和当前任务通知服务 | 停在包装依赖缺失，不跳过风格选择和确认 |
| publish | `--platform` 指定平台；抖音、快手、Bilibili 对应上传 Skill | 继续文案准备，真实上传等待所需能力；小红书始终人工交接 |

下载器、外部 Skills 和桌面应用不包含在基础包，也不自动承诺其当前可用、免费或跨平台。安装来源与版本由维护者的依赖清单或使用者明确提供；未知来源不自动下载。账号信息由对应工具管理，运行配置不保存令牌、密码或 Cookie。

## 调用路径

文档中的 `scripts/...` 相对当前 Skill 目录；`shared/...` 相对包根目录。工作项目可以位于任何路径，调用脚本时先解析已安装 Skill 的位置，不把工作项目误当作 Skill 仓库。不要求使用者把资料搬进安装目录。
