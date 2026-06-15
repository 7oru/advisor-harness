# Routing Policy

Advisor should be invoked when any of the following are present:

- Executor explicitly emits an advice request.
- Executor emits a memory proposal.
- A security questionnaire answer makes a high-risk security, privacy, compliance, or legal-adjacent claim.
- An answer is affirmative but has no evidence.
- Sources conflict or appear stale.
- Executor marks low confidence.
- Post-run review is requested.

Advisor packets must be narrow and structured. Do not send an unbounded transcript when a focused packet is enough.
