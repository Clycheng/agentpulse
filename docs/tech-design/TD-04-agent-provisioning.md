# TD-04：Agent 供给（一句话 → 定制员工）

- 关联：[DATA-MODEL §6](DATA-MODEL-AND-API.md)(权威 schema/API)、[ARCHITECTURE-DETAILED.md](ARCHITECTURE-DETAILED.md) §5.1(时序)、[agent-model-and-capabilities.md](agent-model-and-capabilities.md) §3(数据流)、[TD-05](TD-05-capability-catalog.md)(前置积木)
- ⚠️ 执行会话：**大部分任务纯 `services/api`(任意会话)**；只有 T6(真实写 Hermes profile)必须在 agentpulse 锚定会话做。

## 技术设计

### 目标
用户说"我要一个前端工程师，能写代码、发 PR、部署预览"→ 系统自动产出一个**配置完整的员工**：结构化 role_spec 落库、SOUL.md 生成、能力(技能/toolsets/MCP)按 catalog 授予、缺的凭证向用户索要、就绪后出现在组织架构。

### 两个关键架构决策

**决策 A：v1 入口是"创建员工表单"，不是聊天。** 聊天里对小秘说"我要个前端工程师"→小秘起草 role_spec 的路径，依赖 TD-02 的讨论编排，**放到 TD-02 之后叠加**。v1 先做：桌面端"创建员工"弹窗加一个 NL 描述框 + 可勾选的能力清单(来自 catalog)，后端用 LLM 起草缺省项。这样 TD-04 完全不依赖 TD-02，可并行。

**决策 B：供给分两段，接缝正好切在〔待核〕边界上。**
- **逻辑供给(纯后端，v1 全部可做可测)**：建 `agents`+`agent_specs`+`agent_capabilities` 行、LLM 起草/校验 role_spec、生成 SOUL.md 文本(存 DB/文件)、凭证状态机。
- **物理供给(碰 Hermes，须验证会话)**：真的 `profile create`、写 SOUL.md/config.yaml/.env、装技能。抽象成接口：

```python
# services/api/app/runtime/profile_provisioner.py〔新增〕
class ProfileProvisioner(Protocol):
    def create_profile(self, profile_name: str) -> None: ...
    def write_soul(self, profile_name: str, soul_md: str) -> None: ...
    def configure(self, profile_name: str, *, model: str,
                  toolsets: list[str], mcp: list[str]) -> None: ...   # 〔语法待核〕
    def install_skills(self, profile_name: str, skills: list[str]) -> None: ...  # 〔待核〕
    def write_credentials(self, profile_name: str, creds: dict[str, str]) -> None: ...

class RecordOnlyProvisioner:   # v1/测试用：只把动作记进表，不碰 Hermes
class LocalHermesProvisioner:  # T6：真实现，Hermes 验证会话完成
```
这样除 T6 外的一切都能先做完并被单测覆盖；T6 换实现类即可，其余代码零改动。

### 供给状态机（`agent_specs.status`，见 DATA-MODEL §6.1）
```
draft ──provision()──▶ provisioning ──全部能力 enabled──▶ ready
                          │  存在 credential_missing
                          ▼
              blocked_on_credentials ◀──▶ (用户补凭证逐项解锁)
   任一步异常 ──▶ failed（可重试 provision()，幂等）
```

### role_spec 起草（`orchestration/provisioning.py::draft_role_spec`〔新增〕）
- 输入：`role_name` + `source_request`(NL) + 用户勾选的 `capability_keys`(可空)。
- LLM(走现有临时执行层 `runtime/deepseek.py`)按提示词产出：`responsibilities[]`(≤12) + 建议的 `capability_keys[]`。
- **硬校验(代码，不信 LLM)**：`validate_capability_keys()`(TD-05)；未知 key 直接剔除并记录；risk_gate 一律以 catalog 为准(LLM 无权决定)。
- 用户勾选与 LLM 建议**取并集**，最终清单展示给用户确认后才 provision。

### SOUL.md 生成（`draft_soul_md`〔新增〕）
- LLM 模板输入：role_name / responsibilities / 公司名 / 产品北极星里的行为规范("背景不清先问"等)。
- 输出存 `agent_specs` 关联(v1 存文件 `<data_root>/souls/<agent_id>.md` + DB 记路径，物理供给时拷进 profile)。
- 可参考 agency-agents 对应人格改造(见 [skill-source-repos.md](../research/skill-source-repos.md))；**注意 ADR 0005：SOUL 规则是引导不是保障**，别在这里承诺行为。

### 凭证流（安全边界，严格照 DATA-MODEL §6.4）
- `POST /api/agents/{id}/credentials`：value **不落业务 DB**，直通 `ProfileProvisioner.write_credentials`(即 profile 的 `.env`)；DB 只把该 capability `credential_missing→enabled`。
- 日志/错误信息**绝不回显 value**。
- `prohibited_auto` 能力(如 domain_register)**不收凭证**——它根本不自动执行，UI 直接显示"此能力需老板亲自操作"。

### 幂等与并发
- `provision()` 可重复调用：按 capability 逐项检查 status，只补做未完成项。
- `profile_name` 生成规则：`wk<workspace前6>-<agent前6>`(DATA-MODEL §6.1)，建前查重。

### 开放问题（实现前定/验证会话定）
1. LLM 起草质量：提示词要在 T3 里迭代，验收含 3 个真实用例(前端工程师/小红书运营/财务助理)。
2. `configure()`/`install_skills()` 的真实 Hermes 语法〔待核〕→ T6。
3. v1 是否给"能力清单确认"单独一步 UI(建议：是，供给前让用户看到将授予什么+要什么凭证)。

## Tech-Tasks

### TD-04-T1：新表 + DTO（严格照 DATA-MODEL §6.1/6.2）
- 改动点：`agent_specs`/`agent_capabilities` 建表——**`init_postgres()` 和 `init_sqlite()` 两处都加**(G4)；`schemas/agent_spec.py` 新增 `AgentSpecOut`/`AgentCapabilityOut`/`RoleSpecIn`。
- 验收：单测覆盖建行/状态 CHECK 约束/UNIQUE(agent_id,capability_key)；两方言都过。
- 依赖：TD-05-T1。需 agentpulse 会话：否。估算：0.5 天。

### TD-04-T2：ProfileProvisioner 接口 + RecordOnlyProvisioner
- 改动点：`runtime/profile_provisioner.py` 接口 + record-only 实现(动作写入一张审计用 `provisioning_actions` 内存/表记录，供测试断言)。
- 验收：单测——供给流程调用序列可被断言；不产生任何真实文件/进程副作用。
- 依赖：无。需 agentpulse 会话：否。估算：0.5 天。

### TD-04-T3：role_spec 起草 + SOUL 生成
- 改动点：`orchestration/provisioning.py`：`draft_role_spec()`(LLM+硬校验) / `draft_soul_md()`。
- 验收：单测(mock LLM)——未知 capability_key 被剔除；risk_gate 不可被 LLM 放宽；3 个真实用例的人工评审通过(提示词迭代)。
- 依赖：TD-05-T1。需 agentpulse 会话：否。估算：1 天。

### TD-04-T4：供给编排 + 状态机
- 改动点：`provision(agent_id)`——按 §状态机推进；逐能力检查凭证；调 ProfileProvisioner；幂等可重试。
- 验收：单测——缺凭证→blocked_on_credentials；补齐→ready；中途失败→failed 且重试只补做剩余项。
- 依赖：T1,T2,T3。需 agentpulse 会话：否。估算：1 天。

### TD-04-T5：API 路由 + 前端最小闭环
- 改动点：按 DATA-MODEL §6.4 实现 4 个接口(`POST /api/agents` 扩 role_spec、`GET .../spec`、`POST .../credentials`、`POST .../provision`)；桌面端"创建员工"弹窗加 NL 描述框 + 能力确认步 + 缺凭证清单展示。
- 验收：端到端(可用 RecordOnlyProvisioner)——表单→spec 落库→确认能力→补一个凭证→ready；凭证 value 不出现在任何响应/日志。
- 依赖：T4。需 agentpulse 会话：手测起服务时是。估算：1.5 天。

### TD-04-T6：LocalHermesProvisioner 真实现〔须 agentpulse 锚定会话〕
- ✅ **前置语法已全部实测**(2026-07-08 [验证报告](../research/hermes-verification-2026-07-07.md) V1/V2/V3/V6，已回填 [DATA-MODEL §5.3](DATA-MODEL-AND-API.md))，本任务已解除阻塞：
  - `configure()`：toolsets 用 `hermes tools enable|disable <真名>`；MCP 用 `hermes mcp add <name> --url/--command ... --env KEY=VALUE`。
  - `install_skills()`：`hermes skills install <github-path|url>` / `skills tap add <repo>`，落 `profiles/<name>/skills/`。
  - 工种模板可用 `profile export/import/install`；⚠️ **import 会写 wrapper 到 `~/.local/bin/`，供给流程完成后必须删除该 wrapper**(实测踩过)。
- 改动点：真实 `hermes profile create --no-alias` + 写 SOUL.md + 上述 configure/install_skills + `.env` 凭证写入。
- 验收：真实建出一个"前端工程师" profile，`hermes -p <name> -z "你是谁"` 人格生效；toolsets/MCP 配置在 config.yaml 里可见且 gateway 起得来。
- 依赖：T4；**必须 agentpulse 锚定会话**(ADR 0005)。估算：1–1.5 天(含语法探明)。

## Definition of Done
- 全链路：表单 NL → role_spec 确认 → 供给 → 补凭证 → ready，RecordOnly 与真实 Provisioner 双路径可切换；凭证零落库零回显；〔待核〕项全部补实并回填 DATA-MODEL/TD-05。
- 更新 AGENTS.md §4 / CHANGELOG / 本文件状态。
