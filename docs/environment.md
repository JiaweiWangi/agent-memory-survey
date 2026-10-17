# 执行环境实录

最后核验：2026-10-17（G0）。本文件记录实测结果，不记录推测；能力变化时更新并注明日期。

## 1. 基础环境

| 项 | 实测值 |
|---|---|
| 操作系统 | macOS (Darwin 25.2.0, arm64) |
| 包管理 | Homebrew 7.0.4（`/opt/homebrew/bin/brew`） |
| Python | uv 0.11.17 管理；项目 Python 3.12.13（uv 本地已有） |
| 依赖 | httpx、pydantic、pypdf、pytest（`uv.lock` 锁定） |
| 网络 | curl/jq 可用；无代理环境变量 |

## 2. 学术检索与全文获取（2026-10-17 实测）

| 来源 | 状态 | 实测细节与对策 |
|---|---|---|
| OpenAlex API | ✅ 可用 | 主题检索正常（`search=LLM agent long-term memory` 返回 40,575 条）；加 `mailto` 参数进礼貌池 |
| arXiv API | ✅ 可用（需节流） | 连续快请求返回 `Rate exceeded.`；单请求正常（Atom XML 完整）。对策：≥3s 间隔 + 指数退避 + 响应缓存 |
| Semantic Scholar API | ⚠️ 限流 | 返回 `429 Too Many Requests`；仅作增益源，退避重试，失败不阻塞 |
| arxiv.org/abs、/html | ✅ 可达 | HTTP 200；HTML 全文按章节提取 |
| ar5iv.labs.arxiv.org | ✅ 可达 | HTTP 200；作 HTML 备用通道 |

## 3. 模型后端（2026-10-17 实测）

- 端点：环境变量 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`（Anthropic 兼容 Messages API）。
- 冒烟测试：curl 直连 `/v1/messages` 最小请求成功返回（`stop_reason=end_turn`）。
- 凭证只从环境变量读取，不写入任何文件、配置样例或日志。
- 模型名从 `ANTHROPIC_DEFAULT_*_MODEL` 环境变量取；适配器记录实际 model 标识、参数与 usage。

## 4. LaTeX 与 PDF 工具（2026-10-17 安装并冒烟通过）

| 工具 | 状态 |
|---|---|
| tectonic 0.17.0 | ✅ 已装；最小 `ctexart` 文档（中文正文 + natbib 引用 + 参考文献）编译成功 |
| poppler (pdftotext/pdfinfo) | ✅ 已装；MemGPT PDF (2310.08560, 13 页) 页级提取正常（`-f N -l N` 定位到 Table 2/3） |
| 中文字体 | ctex 自动检测本机字体链路可用；Songti.ttc 存在（`/System/Library/Fonts/Supplemental/`） |

## 5. 项目启动方式

```bash
cd Acdamic-Writing-Class-Task
uv sync                        # 按 uv.lock 恢复环境
uv run litreview --help        # CLI 入口（src-layout，[project.scripts]）
uv run pytest                  # 测试
```

模型凭证：`export ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=...`（参照 `.env.example` 变量名，值不入库）。

## 6. 已知缺口与替代路径

| 缺口 | 影响 | 替代路径 |
|---|---|---|
| Semantic Scholar 限流 | 增益检索可能不可用 | OpenAlex + arXiv 已满足"两个来源"要求 |
| Crossref 未实测 | DOI 核验多一路径 | OpenAlex 元数据含 DOI；正式页人工核验兜底 |
| 模型端点配额未知 | 大批量运行成本不可估 | 缓存 + 分批 + 单回合步数上限；实测用量后估算 |

## 7. 待办

（无——G0 冒烟已全部通过；新增缺口随时补录本表。）
