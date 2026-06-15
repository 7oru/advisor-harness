# Multi-Agent Advisor Architecture

## 1. 架构目标

本架构服务于 Security Questionnaire Advisor，同时保持 harness 可复用于其他垂类。

核心原则：

- 业务先行，架构内化。
- Executor 负责低成本主流程。
- Advisor 负责稀缺高价值判断。
- Memory 必须受控写入。
- Agent 间不自由长对话，所有交流经过 harness 和结构化 packet。

## 2. 总体设计

```text
User task
  -> Harness creates run
  -> Executor role builds prompt
  -> Kimi CLI adapter runs task
  -> Harness parses output and proposals
  -> Routing policy decides advisor calls
  -> Advisor role builds review packet
  -> Codex CLI adapter reviews packet
  -> Harness writes artifacts, approved memory, outcome
  -> Post-run review generates feedback
```

Harness 是唯一调度者。Executor 和 Advisor 不直接互相调用，也不直接写长期 memory。

## 3. Repo 结构

MVP 使用一个 monorepo，业务产品和通用 harness 放在同一个 repo 中，但目录边界清晰。

```text
multi-agent-advisor/
  prd.md
  architecture.md
  README.md
  AGENTS.md
  .gitignore

  apps/
    security_questionnaire/
      prompts/
      workflows/
      sample_inputs/
      sample_outputs/

  packages/
    harness/
      cli.py
      runner.py
      policy.py
      memory.py
      artifacts.py
    adapters/
      base.py
      codex_cli.py
      kimi_cli.py
    roles/
      executor.py
      advisor.py

  policy/
    routing_policy.md
    post_run_review.md

  memory/
    README.md
    schema.json
    facts.jsonl          # gitignored by default
    decisions.jsonl      # gitignored by default
    episodes.jsonl       # gitignored by default

  mailbox/               # gitignored
    advice_requests.jsonl
    advice_responses.jsonl
    memory_proposals.jsonl

  runs/                  # gitignored
    <run_id>/
      task.md
      executor.stdout.txt
      executor.events.jsonl
      advisor_reviews.jsonl
      memory_proposals.jsonl
      outcome.json
      post_run_review.md
      policy_patch_proposal.md
```

## 4. Adapter 与 Role 边界

Adapter 按 backend/CLI 分，Role 按语义职责分。

```text
adapters/
  codex_cli.py   # 怎么调用 Codex CLI
  kimi_cli.py    # 怎么调用 Kimi CLI

roles/
  executor.py    # 怎么执行主任务
  advisor.py     # 怎么审核 packet
```

不要做 `CodexAdvisorAdapter` 或 `KimiExecutorAdapter` 这种混合抽象。后续应允许：

```yaml
roles:
  executor:
    backend: kimi
  advisor:
    backend: codex
```

也应允许未来反转或替换：

```yaml
roles:
  executor:
    backend: codex
  advisor:
    backend: kimi
```

## 5. Adapter 接口

MVP 的最小接口：

```python
class AgentAdapter:
    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        session_id: str | None = None,
        output_schema: str | None = None,
        timeout_seconds: int | None = None,
    ) -> AgentResult:
        ...
```

`AgentResult` 至少包含：

```python
class AgentResult:
    stdout: str
    stderr: str
    final_message: str
    events_path: str | None
    exit_code: int
    session_id: str | None
    raw_artifacts: dict
```

Adapter 只负责：

- 命令构造。
- cwd/session/env。
- stdout/stderr/raw events 保存。
- timeout 和 exit code。
- CLI 版本差异隔离。

Adapter 不负责：

- 判断是否需要 advisor。
- 审核 memory。
- 理解业务问题。
- 修改 routing policy。

## 6. 已确认 CLI 能力

### 6.1 Kimi CLI

本机已确认：

- `kimi --print`
- `kimi --quiet`
- `kimi --session`
- `kimi --continue`
- `kimi --output-format stream-json`
- `kimi --work-dir`

MVP 首选：

```bash
kimi --work-dir <repo> --print --final-message-only --prompt "<prompt>"
```

如果需要保留 session：

```bash
kimi --work-dir <repo> --session <session_id> --print --prompt "<prompt>"
```

### 6.2 Codex CLI

本机已确认：

- `codex exec`
- `codex exec --json`
- `codex exec --output-schema`
- `codex exec resume`
- `codex --cd`

MVP 首选：

```bash
codex exec --cd <repo> --json --output-last-message <file> "<prompt>"
```

后续可使用 `--output-schema` 强制 advisor 输出结构。

## 7. Role 设计

### 7.1 Executor Role

ExecutorRole 负责：

- 读取任务和受控 memory summary。
- 读取 routing policy 摘要。
- 拼接 main agent prompt。
- 调用 executor backend。
- 解析 structured blocks。
- 生成 advice request 和 memory proposal。

Executor prompt 必须包含：

- 当前任务。
- 可用 memory summary。
- 当前 routing policy 摘要。
- 何时必须提出 advice request。
- Memory proposal 格式。
- 禁止直接写长期 memory。

### 7.2 Advisor Role

AdvisorRole 负责：

- 审核 advice request。
- 审核 memory proposal。
- 执行 post-run review。
- 输出 policy patch proposal。

Advisor prompt 必须包含：

- 它不是主执行者。
- 它只 review 当前 packet。
- 输出必须可被 harness 解析。
- 若 context 不足，明确说明缺口，不要编造。
- Memory 审核要关注事实性、可复用性、来源、过期性和隐私风险。

## 8. Harness 命令

### 8.1 初始化

```bash
maa init
```

效果：

- 创建 `memory/`、`policy/`、`runs/`、`mailbox/`。
- 写入默认 routing policy。
- 写入 memory schema。
- 检查 `codex` 和 `kimi` CLI 是否存在。

### 8.2 通用任务运行

```bash
maa run "任务描述"
```

效果：

- 创建新的 run id。
- 读取 memory summary。
- 调用 executor。
- 保存 raw artifacts。
- 解析 proposal。
- 按 policy 触发 advisor。

### 8.3 安全问卷任务运行

```bash
maa run-security-questionnaire questionnaire.xlsx --knowledge ./company_knowledge
```

效果：

- 使用 security questionnaire workflow。
- 生成答案草稿、证据链接、风险标记和开放问题。
- 对高风险 packet 触发 advisor。

### 8.4 Post-run Review

```bash
maa review --run <run_id>
```

效果：

- 调用 advisor review run packet。
- 输出 missed/unnecessary advice 判断。
- 输出 memory proposal 质量判断。
- 输出 policy patch proposal。

## 9. Mailbox

Mailbox 是 agent 之间的结构化消息队列。MVP 用 JSONL 实现。

### 9.1 Advice Request

```json
{
  "id": "adv_req_...",
  "run_id": "...",
  "reason": "high_risk_security_claim",
  "task": "...",
  "packet": {},
  "created_at": "ISO-8601"
}
```

### 9.2 Advice Response

```json
{
  "id": "adv_res_...",
  "request_id": "adv_req_...",
  "decision": "approve|revise|reject|escalate_to_human",
  "rationale": "...",
  "suggested_change": "...",
  "created_at": "ISO-8601"
}
```

### 9.3 Memory Proposal

```json
{
  "id": "mem_prop_...",
  "run_id": "...",
  "type": "fact|decision|preference|episode|anti_pattern",
  "content": "...",
  "source_excerpt": "...",
  "confidence": 0.0,
  "expires_at": null,
  "tags": []
}
```

## 10. Memory

Memory 不等于 transcript。Memory 只保存可复用、经过审核、来源清楚的事实、决策、偏好和经验。

长期 memory 记录最小字段：

```json
{
  "id": "mem_...",
  "type": "fact|decision|preference|episode|anti_pattern",
  "content": "...",
  "source_run": "...",
  "source_excerpt": "...",
  "confidence": 0.0,
  "approved_by": "codex|human|rule",
  "created_at": "ISO-8601",
  "expires_at": null,
  "tags": []
}
```

写入流程：

1. Executor 生成 memory proposal。
2. Harness 写入 `mailbox/memory_proposals.jsonl`。
3. Advisor 审核 proposal。
4. Harness 根据审核结果写入 `memory/*.jsonl`。

MVP memory 文件：

- `facts.jsonl`：稳定事实。
- `decisions.jsonl`：项目或公司决策。
- `episodes.jsonl`：任务经验、失败模式、客户追问。

## 11. Routing Policy

当满足以下任一条件时，harness 可触发 advisor：

- Executor 显式提出 advice request。
- Executor 提出 memory proposal。
- 安全问卷答案涉及高风险安全承诺。
- 答案无证据但语气肯定。
- 历史答案冲突。
- 连续失败或测试失败达到阈值。
- Executor 输出包含低置信度标记。
- run 结束后的 post-run review。

Codex 输入应是窄 packet，而不是完整无限 transcript：

```json
{
  "run_id": "...",
  "task": "...",
  "reason": "memory_proposal_review",
  "relevant_context": "...",
  "proposal": {},
  "expected_output_schema": "..."
}
```

## 12. Structured Output

MVP 可先要求 Executor 输出固定 Markdown block：

```text
<ADVICE_REQUEST>
...
</ADVICE_REQUEST>

<MEMORY_PROPOSAL>
...
</MEMORY_PROPOSAL>
```

后续升级：

- Kimi 使用 `--output-format stream-json`。
- Codex 使用 `--output-schema`。
- Harness 使用 schema validation。

## 13. Post-run Feedback Loop

每次 run 结束后，Advisor 判断：

- Executor 是否该更早请求 advice。
- Executor 是否请求了不必要的 advice。
- Memory proposal 是否过度总结、事实错误或缺少来源。
- 哪些 routing policy 应该强化。
- 哪些 prompt 指令导致了无效行为。

输出：

```text
runs/<run_id>/post_run_review.md
runs/<run_id>/policy_patch_proposal.md
```

MVP 不自动改 policy。只生成建议：

```markdown
## Suggested Routing Policy Patch

### Add
- 当 Executor 对高风险安全承诺无证据但仍输出肯定答案时，必须请求 Advisor review。

### Remove
- 删除过于泛化的“遇到不确定就请求 advice”规则。

### Rationale
...
```

## 14. 安全与隐私

- 默认不提交 `runs/`、`mailbox/`、真实 `memory/*.jsonl`。
- 不打印 API key、auth token、CLI 凭证。
- Advisor 每次调用都记录 reason 和 cost proxy。
- Harness 失败时保留中间 artifacts，便于复盘。
- Memory 写入必须可追溯到 source run。
- 自动改 policy 和自动改代码必须保持人工确认。

## 15. 主要风险

### 15.1 Memory 污染

错误、过度泛化或隐私敏感的信息被写入长期 memory，会跨 session 放大。

缓解：

- proposal-only 写入。
- Advisor review。
- source excerpt 必填。
- confidence 和 expires_at 必填。

### 15.2 贵模型调用失控

Advisor 触发过多会失去便宜主流程的意义。

缓解：

- 每次调用记录 reason。
- post-run review 标注 unnecessary advice。
- policy patch 逐步收紧。

### 15.3 Transcript 过长

把完整对话丢给 Advisor 会成本高、噪声大。

缓解：

- packet 化 review。
- run summary。
- relevant context 截断。

### 15.4 CLI 输出不稳定

Codex/Kimi CLI 版本变化可能破坏 parser。

缓解：

- adapter 层隔离。
- 保存 raw stdout/stderr。
- 优先使用 JSON/stream-json/output-schema。

## 16. 实现建议

第一版用 Python 实现 CLI harness。理由：

- 文件系统和 subprocess 编排简单。
- JSONL/schema validation 容易。
- 后续接 SQLite、rich logging、pytest 都方便。
- 不需要前端和服务端，项目复杂度低。

MVP 的第一条主线保持非常窄：

> Kimi 主执行，Codex 只审高风险 packet、memory 写入和 advisor 触发时机。

只要这条主线稳定，后续再扩展更多 agent、更多模型、自动 policy patch 和 UI。
