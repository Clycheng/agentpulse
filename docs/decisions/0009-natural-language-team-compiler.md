# ADR 0009：自然语言团队编译器（一段话 → N 个真实员工）

- 状态：已接受，已实现
- 日期：2026-07-20
- 关联：[ADR 0008](0008-human-in-the-loop-approval-model.md)（能力授予/供给复用同一套 capability_catalog）、[TD-04-T3](../tech-design/TD-04-hermes-supply.md)（`draft_role_spec`/`build_role_spec_prompt`，本 ADR 首次接上生产入口）

## 背景 / 问题

项目所有者的终极目标（比现有"创建员工/人才市场按模板招"更进一步）：**普通老板不会写 prompt/挑能力 key，但能用一段大白话描述自己需要的团队**（例如"我同时管民政局居家养老项目和一个抖音号，需要一个质检、一个运营、一个文案……"）。这一步要把自然语言描述编译成一批**可编辑草稿**，确认后一次性建成真实员工并拉进一个群。

调研 `service-claw-cloud`（同机另一个真实项目，仅供架构参考，零代码/文件复用）时，其"自然语言 → 编译层 → 试运行 → 执行"四段流水线给了初始灵感，但项目所有者在评审时明确否决了其中三点，理由记录如下（决定了本 ADR 的最终形状）：

1. **不做多群自动规划**——"群是老板自己拉的"。系统只在批量创建时自动建**一个**团队大群（这批人本来就是同一次招聘），后续按任务拉小群仍是老板手动操作，不由编译器规划协作图。
2. **业务技能内容不由 LLM 编造**——具体 SOP/业务规则应由老板或小秘后续在对话/资料库里补充，编译器只负责"生成人"（角色、职责、能力 key），不生成业务技能内容。
3. **不加独立校验器阶段**——能力 key 的合法性校验在 `capability_catalog.validate_capability_keys` 里已经存在（`provision_new_agent` 内部会兜底过滤非法 key），单独一层"校验器"是重复建设。
4. **不做试运行/模拟讨论阶段**——项目所有者本人操作风格是"先看草稿、手动改、确认即生效"，不需要额外的模拟对话来验证效果；过度设计会拖慢"最后一公里"的直达感。

## 决定

**团队编译器 = 现有单人招聘链路的批量版本，而非新的执行栈：**

1. **`provision_new_agent`**（`app/services/workspace.py`）从 `_provision_recruited_agent` 泛化而来，成为唯一的"角色规格 + 能力 key → 真实 Hermes 员工"入口。人才市场模板招聘（`recruit_from_template`）、默认秘书 bootstrap、小秘工具 `create_employee`、团队编译器，四条路径现在都调用同一个函数——不重复实现供给逻辑。
2. **`app/orchestration/team_compiler.py`**：`build_team_draft_prompt` + `parse_team_draft`，把一段自然语言编译成结构化草稿列表。复用（而非重写）TD-04-T3 早已实现但从未接生产入口的 `draft_role_spec`（角色职责/能力建议的逐人精修），编译器只负责"拆出几个人、每人叫什么/哪个部门"这一层，单人的职责/能力细化仍走已验证的老逻辑。
3. **两阶段 API**（`app/api/routes/team_compiler.py`）：
   - `POST /agents/draft-team`：调 LLM，返回草稿，**不落库、无副作用**——老板/小秘在前端可编辑每个人的姓名/部门/职责/能力 key 后再确认。
   - `POST /agents/create-team`：对草稿列表逐个走 `provision_new_agent`，全部成功后（若 >1 人）自动建**一个**群把所有新员工拉进去、发系统消息。单人则不建群（不产生"自己一个人的群"这种噪音）。
4. **小秘工具升级**（`app/tools/registry.py`）：`create_employee` 工具 schema 新增 `responsibilities`/`capability_keys`，新增 `list_capabilities` 工具，让小秘在对话里被要求招人时，能先查目录、再用同一条 `provision_new_agent` 路径真建人——而不是只挂名字的纸片员工。
5. **`DeepSeekChatClient.complete()`** 新增 `system_prompt_override` 参数：团队编译提示词要求"严格输出 JSON"，如果照旧套用 `build_system_prompt()` 的"AI 员工回复老板"人设框架（语气规则、"不要假装已发邮件"等），会稀释这条强指令。此参数让任何非对话式工具调用都能跳过人设包装。

## 前端

`apps/desktop/src/main.tsx` 新增 `TeamCompilerModal`：员工花名册页头"描述你的团队"按钮 → 一段话输入 → 生成的草稿卡片（姓名/岗位/部门/描述/职责逐行编辑、能力 key 以可移除 chip + 选择器新增，选择器复用员工详情"+ 授予能力"已有的 `/api/capabilities` 拉取模式）→ 确认后调用 create-team、成功后跳转进新群（单人则跳去花名册）。

## 理由

- **不新增执行栈**：Hermes 仍是唯一运行时（ADR 0001），编译器只是"更好的 create_agent 参数生成器"，产物依旧是真实 Hermes profile，不是编译器自己的新抽象。
- **复用胜过重写**：`draft_role_spec`/`provision_new_agent`/`capability_catalog` 全部是已验证代码路径的复用，符合仓库"三行重复好过过早抽象"的原则，也避免了 TD-02 曾经出现过的"逻辑写了但生产入口没接上"的漂移。
- **克制的产品边界**：四点否决（不规划群图、不编业务技能、不加校验层、不做试运行）都来自项目所有者对"这个人操作风格快、会立刻手动纠偏"的判断——过度设计的中间层对这类用户是负收益，不是稳妥。

## 验证

- 单测：`tests/test_team_compiler.py`（9 例，覆盖 parse 的正常/异常路径 + draft-team/create-team 两个端点，含"部分能力缺凭证"混合 bundle 场景）+ `tests/test_function_loop.py` 新增 2 例（小秘 `create_employee` 真供给 + `list_capabilities` 返回目录）。全量 288 通过（3 个已知与本次改动无关的预存失败，见 CHANGELOG）。
- 真机：`AGENTPULSE_HERMES_PROVISIONING=true` + 真 DeepSeek key，浏览器里走完整链路——输入项目所有者本人给出的养老+抖音场景描述 → 生成 3 人草稿（质检/运营/文案，能力 key 逐人不同）→ 编辑能力 chip → 确认创建 → 3 个真实员工 + 1 个"新团队"群自动建成，`hermes profile list` 可见真 profile；额外用 `curl` 直接调用 `POST /agents/create-team`（单人）验证 `agent_specs.status=ready` + `agent_capabilities` 落库，随即清理测试产生的真实 Hermes profile（未污染既有环境）。

## 后果

- 好处：产品北极星③"自然语言捏 agent"首次有了端到端可用入口；四条招聘路径统一到一个供给函数后，后续任何供给逻辑修改只需改一处。
- 代价/后续：编译器目前只拆"人"，不处理项目所有者原始例子里更复杂的跨角色协作 SOP（如"CMO 机动备援"这种依情况动态支援的角色）——这类精细协作规则仍需老板在群里/资料库里后续补充，属于产品设计的下一步，不在本 ADR 范围。
