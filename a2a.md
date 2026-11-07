# a2a.md — A2A 的 git 协议（产物站 · 指针页）

> **本仓 `ae6623/we-read` 是笔记前台**（静态 Pages），不是服务端。
> A2A 的**协议正文、监听器、任务执行与部署**都在引擎仓 `ae6623/we-read-auto`：
> <https://github.com/ae6623/we-read-auto/blob/main/a2a.md> ·
> <https://github.com/ae6623/we-read-auto/blob/main/AGENTS.md#5-a2a-协作agent-之间怎么说话>
>
> 本页只回答一个问题：**「板子在哪、我该去哪查」**。规则以引擎仓 `a2a.md` 为准，本页不另立一套。

---

## 一句话：A2A 是 git 提交事件板

不是聊天、不是 API 推送、不是实时消息。一方在板文件末尾追加一个消息块并 **push 进 `main`**，
另一方监听 `main` 上的新提交、读写给自己的块、处理后在同一处追加 ACK / DONE 并 push。

**只有进入权威 `main` 的提交才算事件**；本地未 push 的 commit、分支、控制台输出、日志都不算。
**Git 记录 / 提交成功 / 监听命中都不等于消息已送达**，需要通知人的事仍要在 Cue 私聊直报。

## 本仓为什么会有 A2A 文件

前台仓不跑服务，但**全体 Agent 共用的事件日文件物理上放在这里**——这是 auto 仓 `AGENTS.md` §5 的既定约定
（「给人和 book-admin 看的走 agent-communication 日文件」）。所以：

| 谁 | 在哪 | 干什么 |
|---|---|---|
| `ae6623/we-read`（本仓） | 前台 / 静态 Pages | **承载事件板文件**，只放内容与页面；不跑监听、不跑调度、不做业务 |
| `ae6623/we-read-auto` | 服务端 / 唯一代码真相源 | `a2a.md` 协议正文、`comm_watch.py` 监听器、`A2A-*.md` 引擎内部交接、任务执行与部署 |

> 给云端 Agent 发请求、让它去查消息，**发到本仓当日日文件是对的**；不要发到 auto 仓根目录的 `A2A-*.md`
> （那是引擎内部两个 Agent 的交接日志）。

## 板子路径（都在本仓）

| 用途 | 路径 |
|---|---|
| **共用事件日文件**（用户指令 / REQUEST / ACK / DONE / 开跑 / 收尾） | `skills/luoyu-reading/references/agent-communication/YYYY/MM/YYYY-MM-DD.md` |
| 稳定入口索引（只读，**不追加事件**） | `skills/luoyu-reading/references/agent-communication.md` |
| 当月导航（只列链接） | `skills/luoyu-reading/references/agent-communication/YYYY/MM/index.md` |
| 前端专用 A2A 板 | `skills/luoyu-reading/references/frontend-a2a.md` |
| 前端板监听脚本 | `scripts/a2a_frontend_check.py`（`--alias` / `--update` / `--peek N` / `--watch S`） |
| 协议细则 | `skills/luoyu-reading/references/` 下的 `reading-state-protocol.md`（事件通道）、`coordination.md`（串行写入）、`cross-team-coordination.md`（团队/角色别名） |

日文件按 **Asia/Shanghai 当天日期**取；事件一律追加到对应日文件**文末**，只追加、不改写、不删除他人记录。
条目标题：`### [YYYY-MM-DD HH:MM] <团队别名/角色别名> / <run-id 或 task-id> → TO <别名|ALL>`。

## 最小读取流程（会话开工必做）

```bash
git pull --rebase origin main          # 只拉 main；这一步就是「接收事件」
tail -60 skills/luoyu-reading/references/agent-communication/$(date +%Y/%m)/$(date +%Y-%m-%d).md
```
找到 `→ TO <你的别名|ALL>` 且未 ACK 的块 → 按 BODY 执行 → 同一日文件文末追加 ACK / DONE（带 commit sha）
→ 只 `git add` 该文件 → commit → push。被并发拒绝就先拉最新再合并增量，**禁止强推**。

前端板另跑一次：`python scripts/a2a_frontend_check.py --alias <你的别名> --update --peek 5`
（`--peek` 必带——历史上游标短路漏读过两条消息）。

## 监听方式：不用 5 分钟定时任务

服务端**已有** `comm_watch.py`：`python comm_watch.py --watch`（默认 20 秒探测 `origin/main`，
用 `git ls-remote` → fetch → `git log prev..sha` 取新增消息块，命中外部条目即打印全文并唤醒）。
它监听的是**提交内容变化**，比定时读文件可靠也及时；命令与零轮询方案见引擎仓 `a2a.md`。

严格说 Git 没有客户端被动推送，`--watch` 仍是短周期探测；要真·事件驱动需 GitHub Actions `on: push`
或 Webhook 推到云端应用——**这两项属于服务端/平台配置，不在前台仓实现**。
未启用前，`comm_watch.py --watch` 是主通道，会话开始的一次性 `--once` + 看板尾是兜底（常驻任务可能没起来、Agent 可能离线）。

## 铁律

1. 只有 `main` 上的新提交是事件，核对用 `git log origin/main`，不靠索引文件或 roster 推断。
2. Git 记录 ≠ 送达；失败 / 受阻 / 结果不确定必须在 Cue 私聊直报，无发送能力标「待通知」。
3. 只追加、不覆盖他人记录；共享写入前后 `git status` / `git diff --check`。
4. 没读完正文不要推进已读游标；定长轮询必带 `--peek`。
5. 只写适合公开的最少元数据：不写凭据、登录态、内部服务地址、绝对路径、私有日志、书籍全文。
