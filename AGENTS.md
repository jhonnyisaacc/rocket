# Rocket research program

Read `docs/research/RESEARCH_CHARTER.md`, `AUTONOMOUS_RESEARCH_PROTOCOL.md`,
`AGENT_ROLES.md`, and `TRIAL_LEDGER.md` before research work. Follow the
Project at https://github.com/users/jhonnyisaacc/projects/4 and committed
contracts. Project edits alone do not grant experiment admission.

- Keep `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. Never enable orders/trading.
- Select only the highest-priority admitted Ready item whose dependencies and
  unlock conditions are verified. Research WIP is 3 unique primary items;
  linked PRs are evidence, and healthy operational services do not count.
- MOM-002 is Draft, unapproved and unscored. No fitting, association inspection,
  forecasts or scoring until exact independent admission/freeze requirements
  are met. A reviewable proposal freeze is not scoring permission.
- No agent approves or merges its own PR/experiment. Reviewers must not have
  designed or implemented the experiment. Do not invent a reviewer identity.
- Do not invent human economic/risk values or fill them after viewing results.
- Preserve failed trials and use the official scorer and journal. No subjective
  PASS reinterpretation, retries after scorer START, or automatic rescue.
- MOM-002 FAIL rejects the entire downstream BTC branch; no MOM-003 rescue.
- Build data infrastructure only for an admitted experiment or an existing
  correctness bug. No current macro/Cava/X/options-history admission.
- Use a dedicated branch and PR. Never push, force-push or rewrite main.
  Before a push, verify branch/upstream and use an explicit destination such
  as `git push origin HEAD:refs/heads/<verified-working-branch>`.
- Historical PR closure requires preserved evidence, a valid canonical
  replacement, an archive label and an individual closing comment. Do not
  merge runtime changes merely to preserve result documents.
- Offline governance tests use synthetic fixtures only. CI must not acquire
  market data or score a research hypothesis.
