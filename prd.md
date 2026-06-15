# Security Questionnaire Advisor PRD

## 1. 产品定位

Security Questionnaire Advisor 是一个 local-first 的企业安全问卷 / DDQ / RFP 技术问答助手。

目标用户是 20-200 人 B2B SaaS 团队中的 founder、sales engineer、security owner 或 operations owner。产品帮助他们用本地知识库和历史回答，低成本生成安全问卷初稿，并在高风险答案和长期记忆写入时引入贵模型 advisor 审核。

底层使用双 agent advisor harness：

- Kimi 作为 executor，负责低成本拆题、检索、起草和整理。
- Codex 作为 advisor，负责高风险审核、memory 审核和 post-run feedback。

架构细节见 [architecture.md](architecture.md)。

## 2. 问题

B2B SaaS 在进入企业采购流程时，经常需要回答安全问卷、RFI、DDQ、RFP 技术章节或 vendor due diligence 表格。这类工作有几个典型痛点：

- 问题重复但措辞变化大，人工查历史答案很耗时。
- 答案涉及 SOC 2、加密、SSO、备份、数据保留、子处理方、权限、隐私、部署架构等敏感事实。
- 错误回答风险高，尤其是把计划能力写成已实现能力、引用过期证据、承诺不存在的控制项。
- 历史答案、政策文档和客户追问分散在本地文件、表格和聊天记录里。
- 团队不一定愿意把完整安全资料上传到第三方 SaaS 平台。

## 3. 产品目标

### 3.1 MVP 目标

MVP 聚焦一个可验证闭环：

1. 输入一个安全问卷文件和本地公司知识库。
2. Executor 生成答案初稿、证据链接、风险标记和开放问题。
3. Advisor 只审核高风险 packet，而不是全程参与。
4. 任何长期 memory 写入必须先进入 proposal，再由 advisor 或人工批准。
5. 每次任务结束后生成 post-run review，判断是否错过 advisor 介入时机。

### 3.2 非目标

MVP 不做：

- Web UI。
- 多用户协作。
- 云端同步。
- 自动代表公司作出法律或合规承诺。
- 自动修改客户提交文件并直接发送。
- 完整 RFP 管理平台。
- 复杂向量数据库或企业搜索系统。

## 4. 主要用户

### 4.1 Founder / Operator

公司还没有专职安全团队，需要快速但谨慎地完成客户安全问卷。

核心诉求：

- 快速出初稿。
- 不要乱承诺。
- 把常见答案沉淀下来。

### 4.2 Sales Engineer

经常处理客户采购前技术问答，需要复用历史答案并标出需要安全/工程确认的问题。

核心诉求：

- 找到相似历史答案。
- 输出客户可读的答案。
- 标出需要升级的问题。

### 4.3 Security Owner

负责维护事实来源和审核高风险答案。

核心诉求：

- 控制长期知识库质量。
- 避免过期、错误或过度泛化的安全陈述。
- 看见 agent 何时该升级但没有升级。

## 5. 核心工作流

### 5.1 准备知识库

用户提供本地文件夹，例如：

```text
company_knowledge/
  security.md
  privacy.md
  subprocessors.md
  soc2/
  past_answers/
  architecture/
```

MVP 不要求固定格式，但推荐 Markdown、CSV、XLSX、PDF 和 DOCX。

### 5.2 运行问卷任务

用户执行：

```bash
maa run-security-questionnaire questionnaire.xlsx --knowledge ./company_knowledge
```

系统输出：

```text
runs/<run_id>/
  answers_draft.md
  evidence_links.md
  risk_flags.md
  open_questions.md
  memory_proposals.jsonl
  post_run_review.md
```

### 5.3 初稿生成

Executor 负责：

- 拆分问卷问题。
- 识别问题类型和风险等级。
- 查找相关历史答案和证据。
- 生成答案初稿。
- 标注低置信度项。
- 提出 memory proposal。

### 5.4 Advisor 审核

Advisor 只在明确触发时介入：

- 高风险安全承诺。
- 低置信度答案。
- 找不到证据但 executor 给出了肯定回答。
- memory proposal。
- post-run review。

Advisor 输出：

- approve / revise / reject。
- 风险原因。
- 建议答案或建议升级给人工。
- 是否允许写入长期 memory。

### 5.5 人工确认

MVP 阶段所有客户可见答案都默认需要人工确认。系统可以生成草稿，但不负责发送或提交。

## 6. MVP 功能需求

### 6.1 文件输入

MVP 至少支持：

- Markdown 知识库。
- 历史答案 Markdown/CSV。
- 问卷 CSV 或 XLSX。

PDF/DOCX 可作为后续增强。

### 6.2 答案草稿

每个问题输出：

- 原始问题。
- 答案草稿。
- 置信度。
- 证据来源。
- 风险等级。
- 是否需要人工确认。

### 6.3 风险标记

必须标记以下情况：

- 没有证据支持的肯定回答。
- 涉及合规认证、数据驻留、加密、访问控制、备份、日志、保留期、子处理方的答案。
- 历史答案互相冲突。
- 答案来源过旧。
- 使用了 planned、roadmap、partial 等非已实现能力。

### 6.4 Memory Proposal

Executor 只能提出 memory proposal，不能直接写长期 memory。

Memory proposal 应包含：

- 要记住的事实或决策。
- 来源 run。
- 来源摘录。
- 置信度。
- 建议类型：fact、decision、preference、episode、anti_pattern。
- 是否有过期时间。

### 6.5 Post-run Review

每次 run 结束后，Advisor 生成 review：

- 是否存在 missed advisor opportunity。
- 是否存在 unnecessary advisor call。
- 是否存在 bad memory proposal。
- 是否应调整 routing policy。
- 哪些输出需要人工重点检查。

## 7. 验收标准

### Case 1：普通安全问卷初稿

输入一个包含 20-50 个问题的 CSV/XLSX。

期望：

- 生成答案草稿。
- 每条答案有证据来源或 open question。
- 高风险问题被标记。
- run artifacts 完整保存。

### Case 2：拒绝无证据承诺

问卷询问公司是否具备某项安全能力，但知识库没有证据。

期望：

- Executor 不应给出无条件肯定。
- Advisor 应要求 revise 或 human escalation。
- 输出进入 risk flags。

### Case 3：Memory 审核

Executor 提出“公司支持 SSO”的长期 memory proposal。

期望：

- Advisor 检查来源是否足够。
- 若证据明确，批准写入 facts。
- 若证据不足，拒绝或降级为 episode/open question。

### Case 4：错过升级时机

Executor 对高风险合规问题直接生成答案，没有请求 advisor。

期望：

- Post-run review 标出 missed advisor opportunity。
- 生成 routing policy patch proposal。

## 8. 成功指标

MVP 阶段重点看质量和流程闭环，不追求自动化率最大化。

- 对 20-50 题问卷可稳定生成结构化草稿。
- 高风险问题召回率优先于精确率。
- Memory 写入都有来源和批准者。
- Advisor 调用次数可解释。
- Post-run review 能产生可执行 policy 改进建议。

## 9. 迭代路线

### Phase 0：文档和本地骨架

- 完成 PRD 和 architecture。
- 初始化 git repo。
- 确认 Codex/Kimi CLI 可调用。

### Phase 1：单文件问卷草稿

- 支持 CSV/XLSX 输入。
- 支持 Markdown 知识库。
- 输出 answers draft、risk flags、open questions。

### Phase 2：Advisor 审核闭环

- 支持 explicit advice request。
- 支持 memory proposal review。
- 支持 post-run review。

### Phase 3：Memory hardening

- 增加 schema validation。
- 增加 dedupe。
- 增加 source freshness 检查。

### Phase 4：文档格式增强

- 支持 PDF/DOCX 输入。
- 支持回填 XLSX。
- 支持 evidence bundle。

### Phase 5：产品化

- 增加轻量 UI 或 TUI。
- 增加人工 approval queue。
- 增加客户/行业 profile。

## 10. 开放问题

- MVP 是否只支持 CSV/XLSX，还是第一版就引入 PDF/DOCX？
- 知识库是否需要强制 metadata，例如 owner、last_reviewed、valid_until？
- Advisor 是否默认每次 run 后执行，还是按 cost budget 触发？
- 输出格式优先 Markdown 还是回填原始 Excel？
- 是否需要区分 public answer、internal note 和 legal/security escalation？
