# TD-05：能力映射表 capability_catalog

- 关联：[DATA-MODEL §6.3](DATA-MODEL-AND-API.md)(权威种子)、[agent-model-and-capabilities.md](agent-model-and-capabilities.md) §4(能力→积木的论证)、[ARCHITECTURE-DETAILED.md](ARCHITECTURE-DETAILED.md) §4.1/§5.1
- 定位：**系统级静态资产**——把"能力词"翻译成具体 bundle(技能+toolsets+MCP+凭证+风险门)的唯一登记处。TD-04 供给流程的前置积木。
- ⚠️ 执行会话：纯 `services/api` 代码+单测，任意会话可做。

## 技术设计

### 目标
一个代码内常量模块 + 校验函数，让"用户要一个会 X 的员工"能被确定性地翻译成可供给的 bundle，且**安全约束(risk_gate)不由 LLM 决定、由 catalog 硬编码兜底**。

### 为什么是代码常量而不是数据库表
- 条目少(v1 共 8 个)、变更=产品决策(须过 review)、且 `risk_gate` 是安全边界——放代码里改动走 git review，比放库里被运行时改掉安全。
- 未来若要 workspace 自定义能力，再引入覆盖表(不在本片)。

### 模块：`services/api/app/orchestration/capability_catalog.py`〔新增〕

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CapabilityDef:
    key: str
    description: str                       # 给 LLM/UI 看的一句话
    skills: tuple[str, ...] = ()           # SKILL 名(装进 profile 的 skills/)
    toolsets: tuple[str, ...] = ()         # Hermes toolset 名〔合法值待核，见 §开放问题〕
    mcp: tuple[str, ...] = ()              # MCP server 名〔配置语法待核〕
    required_credentials: tuple[str, ...] = ()
    risk_gate: str = "auto"                # auto | approval | prohibited_auto

CATALOG: dict[str, CapabilityDef] = { ... }   # 种子见 DATA-MODEL §6.3，两处必须一致

def get_capability(key: str) -> CapabilityDef: ...          # 未知 key 抛 ValueError
def validate_capability_keys(keys: list[str]) -> None: ...  # 批量校验，供 API 层用
def resolve_bundle(keys: list[str]) -> dict: ...            # 合并去重多个能力的 skills/toolsets/mcp/creds；
                                                            # risk_gate 取"最严"(prohibited_auto > approval > auto)
```

### 设计规则(硬性)
1. **risk_gate 只升不降**：`resolve_bundle` 合并时取最严格；任何调用方(包括 LLM 起草的 role_spec)**不能放宽** catalog 里的 risk_gate，只能收紧。
2. **`domain_register` 永远 `prohibited_auto`**——花钱+不可逆，按安全规则必须人工，写死。
3. 种子 8 条与 [DATA-MODEL §6.3](DATA-MODEL-AND-API.md) 一字不差；改任何一处必须同步另一处(在两个文件顶部互相注明)。
4. `toolsets`/`mcp` 的具体合法值目前〔待核〕——v1 允许存字符串占位(如 `"terminal"`,`"github"`)，Hermes 验证会话确认真实名称后统一替换并回填 DATA-MODEL。

### 开放问题
- Hermes toolset 的真实枚举名(`terminal`? `code_execution`?)——〔待核〕，Hermes 验证会话跑 `hermes tools list` 抄真名。
- capability 粒度：v1 用 8 个粗粒度 key；细化(如 `git_push` 拆读/写)等真实使用反馈。

## Tech-Tasks

### TD-05-T1：catalog 模块 + 校验/合并函数
- 改动点：新建 `orchestration/capability_catalog.py`(上述接口 + 8 条种子)；`orchestration/__init__.py` 导出。
- 验收：单测——`get_capability` 未知 key 抛错；`resolve_bundle(["write_code","deploy_prod"])` 正确合并且 risk_gate=`approval`；含 `domain_register` 时=`prohibited_auto`；种子与 DATA-MODEL §6.3 逐条一致(可写一个把两边对照的测试常量)。
- 依赖：无。需 agentpulse 会话：否。估算：0.5 天。

## Definition of Done
- 模块+测试合入；DATA-MODEL §6.3 与代码一致；TD-04 可直接 import 使用。
