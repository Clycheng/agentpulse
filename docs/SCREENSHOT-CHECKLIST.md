# README 截图拍摄清单

> 背景：这次会话已经把本地 dev 环境（API :8000 + desktop renderer :5174）跑到一个内容丰富的真实状态——8 个员工（含真实群聊自主招到的 4 个）、一个正在讨论的真群聊、一次真实 Hermes 审批（批准/超时自动拒绝各一次）、一次老板发起的能力授予。这份清单就是照着这个状态拍，不需要重新搭。
>
> AI 助手（Claude）没有能把 Browser 面板截图存成真实 PNG 文件的工具——`screenshot` 只能给它自己看，存不到 `docs/images/`。所以这轮由人工（你或团队）掌镜，按下面清单逐条拍。

## 环境状态（如果要继续/重新拍，先确认这些还在）

- API：`cd services/api && AGENTPULSE_HERMES_PROVISIONING=true .venv/bin/python -m uvicorn app.main:app --port 8000`（cwd 必须锚定在本 worktree，不是 UnitPulse）
- Desktop renderer：`cd apps/desktop && npm run dev:renderer`（http://localhost:5174）
- 登录账号：`founder@agentpulse.demo` / `agentpulse123`（工作区"脉动科技"）
- 语言切换：侧栏最下方"我"上面那个语言按钮（EN ⇄ 中），localStorage key `agentpulse_language`
- 深色模式：侧栏的 Light/Dark/System 三个图标

## 拍摄总原则

- 每张图先把语言切成目标语言（英文截图切 EN，中文截图切 中），再拍。
- 中文截图里对话内容本来就是中文，天然贴合。**英文截图里对话内容会仍是中文**（这次会话是用中文场景搭建的）——如果要英文 README 达到营销级别的"全英文"效果，需要另外用英文重新走一遍"招人→群聊→审批"（会真实消耗 DeepSeek 额度），如果只是想让功能截图"看得懂就行"，直接用当前数据切 EN 导航也可以先凑合。**建议**：先用当前数据出一版（导航英文、对话中文），能上线；有空再考虑重录一版纯英文对话的。
- 分辨率：桌面窗口建议 1280×800 或以上，保证文字不糊。
- 文件命名与保存路径统一放 `docs/images/`，命名规则见下表，中英文各一份（除非注明"共用"）。

## 拍摄清单（按优先级排序，前面几张最重要）

| # | 场景 | 怎么走到这个画面 | 文件名（en / zh） |
|---|---|---|---|
| 1 | **Hero：真实群聊+公司自组建** | Messages → 群「新品上线策划」，滚动到小秘汇报"团队搭建完成"那条消息附近（8 人已就位、四阶段节奏表格清晰可见）。这是当前最强的画面——真讨论、真招聘、真产出。 | `hero-discussion-en.png` / `hero-discussion-zh.png` |
| 2 | **审批卡片：高风险动作三选项** | 私聊「阿工」，往上翻到 13:58 那条消息附近的审批卡（`高风险动作需确认：recursive delete: rm -rf scratch_test2`，"允许一次/永远允许/拒绝"三按钮）。如果想要"待处理"状态（按钮还没点掉）而不是已解决的，需要重新触发一次：给阿工发"请创建一个 xxx 目录然后 rm -rf 删除"，等审批卡出现立刻截图，不要点按钮。 | `approval-card-en.png` / `approval-card-zh.png` |
| 3 | **员工花名册（Org Directory）** | Staff 视图，展示"脉动科技 · 8 AI employees · N departments"，可以点开一个部门展开列表。 | `staff-en.png` / `staff-zh.png` |
| 4 | **人才市场** | Talent Market 视图，首屏卡片列表即可，或者点开一个"Talent profile"详情弹窗更有内容。 | `talent-market-en.png` / `talent-market-zh.png` |
| 5 | **任务看板** | Tasks 视图。目前是空的——先建一条真任务（点 New task，标题"产出智能手表发布物料七件套"，指派给"内容主笔"，关联对话选"新品上线策划"），再截图看板。 | `tasks-en.png` / `tasks-zh.png` |
| 6 | **想法中心** | Ideas 视图。目前是空的——先手动加一条想法（或等 idle-thinking 自动生成，需要 cron 开启，比较慢），再截图。 | `ideas-en.png` / `ideas-zh.png` |
| 7 | **员工详情 · 成长轨迹（含新的"+ 授予能力"）** | Messages → 私聊「阿工」→ 右上角"阿工 · View status"打开详情抽屉，滚动到 Growth trajectory 区，展示 `write_code` + `run_tests` 两个 Enabled 徽章，以及"+ Grant capability"按钮（可以点开选择器一起入镜，展示这是本轮新加的老板发起能力授予功能）。 | `growth-trajectory-en.png` / `growth-trajectory-zh.png` |
| 8 | **运行轨迹 / 审计视图** | 私聊「阿工」右上角"Run trace"按钮，打开后展示真实的 run 列表（至少 3 条：真执行、真批准、真超时過期），点开一条看 run_steps 时间线更好。 | `run-trace-en.png` / `run-trace-zh.png` |
| 9（可选） | **深色模式** | 任意一屏（推荐用 #1 的群聊画面）切到 Dark 主题再拍一张，中英各一张或只拍一张通用。 | `hero-discussion-dark-en.png` / `hero-discussion-dark-zh.png` |
| 10（可选） | **渠道管理** | Channels 视图。目前是空的——先创建一个渠道（选一个类型，填名称）再截图。 | `channels-en.png` / `channels-zh.png` |

## 拍完之后

1. 把文件存进 `docs/images/`，文件名照上表。
2. 用 `pngquant` 或类似工具压缩一下（原图可能几百 KB～1MB+，README 里放 8-10 张图会很重）。
3. 更新 `README.md`（配 `*-en.png`）和 `README.zh-CN.md`（配 `*-zh.png`）的 `## 🖼 Screenshots` / `## 🖼 界面预览` 区块——现有的 `<table>` 2×2 网格布局可以直接扩成更多行，别一张张纵向堆。
4. 旧的 5 张图（`hero-discussion.png` 等，无 `-en`/`-zh` 后缀）在新图接上之后可以删除；接上之前先别删，保证 README 不断链。
