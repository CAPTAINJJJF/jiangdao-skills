# 江导三分身 Skills · 豆包版

版本：V1.0.1。豆包应使用本目录版本。

## 自动获取与安装

读取本目录 `release-manifest.json`，确认 `variant` 为 `doubao`。同步器从仓库自动查找 `doubao/release-manifest.json`，仅获取并安装清单中的 Skills 与 `shared/`，不会默认退回 Codex 版。

供具备本地工具的豆包执行：先确认实际豆包 Skills 目录，再运行本目录的同步器。需要 Python 3.10+。

```bash
python3 sync_doubao.py check
python3 sync_doubao.py sync --dest <实际豆包Skills目录>
```

`--dest` 必须使用实际路径，不要照抄占位符。可用 `--tag v1.0.1` 固定本次版本。已有安装会备份，个人资料与运行配置不属于同步内容。需要恢复上次安装时可用 `rollback --dest <实际豆包Skills目录>`。

也可对已获取的完整仓库目录使用 `--bundle <仓库目录>`，离线校验后安装。版型缺失或校验失败时应停止，不能宣称安装成功。

安装后新开豆包任务，让应用重新识别 Skills，再输入“启动本我分身”“启动操盘手分身”或“启动内容编导分身”。不支持本地工具的豆包环境应说明限制。

[运行配置](shared/runtime-configuration.md) · [配置模板](shared/runtime-config.example.json) · [LICENSE](LICENSE)
