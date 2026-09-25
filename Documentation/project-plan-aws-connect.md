# Capstone Plan (Alternative): AI-Driven Credit Card Servicing Phone Agent on Amazon Connect

## Context

**What is being planned:** The same two-semester undergraduate CS capstone — students build a fully automated, AI-driven conversational phone agent that **answers servicing calls and services the cardholder directly**, with no human on the line unless the agent escalates. This version swaps the from-scratch telephony/voice stack (Asterisk, Pipecat, self-hosted ASR/TTS) for **Amazon Connect** and **Amazon Connect Customer Profiles**, so the team gets a real phone number, real call routing, and a real unified-customer-record service on day one, inside AWS's free-tier/low-cost usage bands.

**Why this trade is worth making.** The original telephony stack (SIP signaling, VAD tuning, streaming ASR partials, self-hosted TTS, an event backbone) is genuinely the highest-risk, most time-consuming part of a voice-agent capstone — "telephony rabbit hole" is a named failure mode in almost every prior write-up of this kind of project. Amazon Connect is a managed contact-center service: claiming a number, building call routing ("contact flows"), wiring in speech recognition via **Amazon Lex**, and recording/transcribing calls are all configuration, not infrastructure. That reclaims several weeks for the part of the project that is actually novel: **can the system be trusted to move money and PII autonomously, with proof.**

**Framing (kept from the original, deliberately generic):** today's self-service phone systems are overwhelmingly decision-tree/DTMF-driven, not reasoning agents, and enterprises broadly report that LLM-based systems introduce new risk the moment they're allowed to *act* rather than just answer — that's the real problem, not "can an LLM hold a conversation." The team should present the project against that generic framing rather than any single company's internal metrics, since none are needed to motivate the work.

**Intended outcome:** a working prototype that answers a real inbound phone call on a real number, authenticates a caller, resolves a defined set of servicing needs autonomously (balance/due-date lookups, payments, address changes, disputes, replacement cards), refuses and escalates when it should, and proves all of that with metrics against a baseline the team also builds (a scripted decision-tree IVR).

**No real customer data, ever. All account and caller data synthetic.**

---

## Cost design — this has to work for ~$0–$50 total

Everything in Semester 1 must map to an AWS Free Tier line item or a cost of a few cents. Paid items (a phone number, per-minute usage, LLM tokens) are metered from week 1 with an AWS Budgets alert, not discovered at the end of the semester.

| Component | AWS service | Typical cost band | Notes |
|---|---|---|---|
| Phone number | Amazon Connect | ~$1–2/month for a claimed DID; toll-free costs more per minute | Claim one number for the whole project; don't churn numbers |
| Inbound/outbound minutes | Amazon Connect | Fractions of a cent per minute at U.S. domestic rates | A semester of dev-scale testing (low hundreds of minutes) should land in low single-digit dollars |
| Speech recognition / NLU | Amazon Lex V2 | Free tier covers a substantial monthly request volume for new accounts | Confirm current free-tier limits before relying on the number — AWS free-tier terms change |
| Compute (fulfillment logic, tool calls) | AWS Lambda | Always-free tier (1M requests + 400K GB-seconds/month) | Effectively free at capstone scale |
| Data store (servicing API mocks, audit ledger, sessions) | DynamoDB | Always-free tier (25GB, 25 RCU/WCU) | Effectively free at capstone scale |
| Unified customer record | Amazon Connect Customer Profiles | Usage-based (per profile, per API call); very small at a 300–500 profile scale | Estimate a few dollars for two semesters of dev traffic |
| LLM reasoning core | Amazon Bedrock (small model, e.g. Claude Haiku or Amazon Nova Micro/Lite) | Pay-per-token, no perpetual free tier | This is the real budget line — see below |
| Real-time transcription, sentiment, redaction | Contact Lens for Amazon Connect | Usage-based, small at this scale | Turns a chunk of custom PCI-redaction work into a checkbox |
| Guardrails (PII/content filtering) | Amazon Bedrock Guardrails | Usage-based, small | No extra infra to host |
| Monitoring | CloudWatch | Free tier covers dev-scale dashboards/alarms | |

**Covering the Bedrock line for free:** secure AWS credits before token usage starts — the **GitHub Student Developer Pack** and **AWS Educate** both routinely include AWS credit grants for enrolled students, and many universities can request classroom AWS credits directly. With a small model and a hard weekly token cap, total Bedrock spend across two semesters should be small enough that a modest credit grant covers all of it — treat that as a week-1 task, not a nice-to-have.

**Standing rule:** every teammate's weekly demo run reports its own cost from Cost Explorer/AWS Budgets. If a milestone can't be demoed within the weekly cap, that's a design problem to fix, not a budget problem to absorb.

---

## Architecture

### Telephony and conversation shell — Amazon Connect

- Claim one real number in an Amazon Connect instance. This is a real PSTN endpoint from week 1 — no separate "tier 3 demo garnish" workaround needed.
- **Contact flows** (Connect's visual call-routing builder) replace the hand-built IVR/dialplan work — branching logic, hours of operation, queueing, and transfer-to-human are configuration.
- **Amazon Lex V2**, embedded directly in the contact flow, provides managed streaming speech recognition, intent/slot filling, and barge-in — this removes the need to hand-roll VAD tuning, streaming ASR partial-hypothesis stabilization, or a self-hosted TTS voice, while still leaving room for a "how good is the managed stack, actually" evaluation chapter (WER, latency, barge-in responsiveness) using the exact same rigor the original plan called for.
- **Contact Lens for Amazon Connect** turns on real-time transcription, sentiment analysis, and built-in sensitive-data redaction for every call — this is the managed analog of a custom PAN/PII scrubber, and should be the primary control; still build a small Luhn-validating CI check over stored transcripts as a defense-in-depth gate, since "the managed control might miss something" is a legitimate finding either way.
- Escalation is a real Connect queue with a rotating teammate on an **Amazon Connect CCP** softphone — an actual transfer-to-human, not a simulation of one.

### Reasoning / tool-calling core

- **AWS Lambda** functions, invoked as Lex fulfillment, host the agent logic: call an LLM on **Amazon Bedrock**, constrained to emit a typed, schema-validated tool call (JSON Schema/Pydantic-equivalent) — never a free-form "effect."
- Tool calls execute against a small set of synthetic servicing APIs (API Gateway + Lambda + DynamoDB): balance/due-date/transaction lookups, payment, address change, dispute filing, replacement card request.
- **The non-negotiable carries over unchanged: the model proposes, a separate deterministic layer decides.** Use **Open Policy Agent (Rego)** — open-source, free, and generic — as that authorization layer, keyed on `(action tier, auth level, risk signals)`.

### Customer/account data — Amazon Connect Customer Profiles

- Seed a synthetic population (300–500 "cardholders," `Faker`, fixed seed) into **Amazon Connect Customer Profiles** as the unified record: identity, contact info, and calculated attributes, with deeper account/transaction detail held in DynamoDB and joined by profile ID.
- The contact flow resolves the caller's profile at call start (by ANI or a spoken account identifier) before the agent logic runs — this gives the team a real "customer 360" service to integrate against instead of hand-rolling a session-authority store, and is the natural place to demonstrate session-level auth-level/consent/budget tracking (closing the same "no unified view of who this caller is and what they're allowed to do" gap the original plan targeted, without needing any internal documentation to motivate it).

### Guardrails (all free or open-source; unchanged in spirit from the original plan)

| Tier | Examples | Gate |
|---|---|---|
| 0 — Read | balance, due date, recent transactions | auth only |
| 1 — Low-risk write | paperless enroll, travel notice, replacement card to address on file | verbal confirm, audit only |
| 2 — Money / PII | payment, autopay, address change, card to new address, credit-limit change, close account | read-back two-phase commit, amount cap, idempotency key, rate limit |
| 3 — Never automated | fraud claim, dispute with provisional credit, collections disclosure, hardship, deceased/estate | mandatory human handoff |

Non-negotiables, each a gradeable artifact:

1. **The LLM never emits an effect** — only a validated tool call; execution is a separate layer. Lint-enforced.
2. **Policy as data** — one OPA/Rego bundle, versioned independently of the agent code.
3. **Read-back confirmation with a non-LLM acceptance test** for every tier-2 action — a constrained yes/no/repair classifier, not the planner's own judgment.
4. **Amazon Bedrock Guardrails** for input/output content filtering, denied topics, and PII detection, layered around the planner call — pairs with Contact Lens redaction rather than duplicating it.
5. **PCI redaction before persistence** — Contact Lens as the primary control, a Luhn-validating CI grep over the audit store as the backstop; the CI job fails the build if it ever finds a Luhn-valid 16-digit run.
6. **Two-party consent gate** before recording begins, resolved from the caller's profile against the public list of two-party-consent states, with disclosure played and acknowledgment recorded.
7. **Append-only, hash-chained audit ledger** (DynamoDB or Postgres) with a `verify_ledger.py` that proves tamper-evidence.

---

## Semester 1

| # | Wks | Deliverable | Acceptance criterion |
|---|---|---|---|
| 1 | 2 | Connect instance + claimed number; contact flow answers and plays a prompt; Lex bot echoes back a transcribed utterance | Fresh AWS account → answered real call in under a day |
| 2 | 2 | Customer Profiles populated with the synthetic population; contact flow resolves caller → profile at call start | 100% of test calls resolve the correct synthetic profile by spoken account identifier |
| 3 | 3 | Agent resolves 3 read-only needs end-to-end (Lex → Lambda → Bedrock planner → typed tool call → DynamoDB mock API → TTS response) | 30/30 scripted calls correct |
| 4 | 3 | Tier-1 writes (paperless, travel notice, replacement card to address on file) + verbal confirm | 8/8 needs pass happy path across held-out scenarios |
| 5 | 3 | **End-to-end demo:** live real call resolves a payment (read-back confirm) and an address change, refuses and escalates a fraud claim to a live queue | 10 consecutive uncut live calls; ≥ 65% task success on 20 held-out scenarios; 0 unsafe actions |

## Semester 2

| # | Wks | Deliverable | Acceptance criterion |
|---|---|---|---|
| 6 | 3 | Full tier-2 gating: OPA bundle, read-back two-phase commit, idempotency, rate limiting | 0 of 60 adversarial attempts executes a tier-2 action without proper gating |
| 7 | 3 | Intent chaining (e.g. payment → address update → autopay in one call) | 6/6 chained scenarios complete without losing the primary intent |
| 8 | 2 | Compliance layer: required-disclosure coverage (Mini Miranda, Reg E error-resolution timing), two-party consent gate, Bedrock Guardrails + Contact Lens redaction verified together | ≥ 95% required-disclosure coverage; consent gate correct on every state case tested |
| 9 | 2 | Red-team campaign: prompt injection, authority spoofing, confirmation bypass, PAN elicitation, amount inflation — run against the live Connect number | 0 unauthorized executions; every attempt logged and classified |
| 10 | 3 | Final: 12–15 needs, evaluation report against the team's own scripted-IVR baseline, reproducibility package, signed safety-claims table | ≥ 55% containment vs. the scripted baseline; 0 unsafe actions across the full held-out set |

---

## Evaluation

Carried over unchanged from the general design, all still meaningful without any company-specific baseline:

- **Unauthorized-action rate** — must be 0, reported as an exact-zero-in-N claim with N stated.
- **Hallucinated-action rate** — executed tool calls absent from the gold scenario trace or with wrong arguments.
- **Task success and containment**, measured against the team's own scripted decision-tree IVR baseline (build this in week 3 — it's the fair comparison point, not a strawman).
- **Escalation precision/recall** — precision matters most; a needlessly escalated call defeats the premise.
- **Disclosure coverage** against the regulatory checklist (Mini Miranda, Reg E timing, two-party consent).
- Latency and call-quality metrics can be pulled directly from **Amazon Connect / Contact Lens analytics** instead of hand-instrumented tracing — one less system to build.

---

## Team roles (5-person default)

| Role | Owns | Accountable for |
|---|---|---|
| **Connect/Conversation** | contact flows, Lex bot, Customer Profiles integration | the caller-facing experience |
| **Agent Core** | Lambda fulfillment, Bedrock planner, tool registry, servicing API mocks | task success |
| **Policy/Safety** | OPA bundle, auth ladder, redaction backstop, audit ledger, red team | "zero unsafe actions" |
| **Data/Eval** | synthetic population, scenario corpus, eval harness | every number in the report |
| **Cost/Ops** | AWS Budgets, credit grants, weekly cost report, CI/reproducibility | staying inside the free/low-cost envelope |

The Cost/Ops role is new relative to a from-scratch build — with a managed telephony stack, the main new operational risk isn't infrastructure, it's runaway usage cost, so someone owns watching it every week.

---

## Risks

- **Real usage costs real money, even if small** — mitigate with a weekly AWS Budgets alert and a hard per-week token/minute cap agreed on in week 1.
- **AWS free-tier terms and Amazon Connect/Lex/Bedrock pricing change over time** — verify current numbers on AWS's own pricing and free-tier pages before locking the budget table above into a report; don't rely on this document's figures as final.
- **Secure student AWS credits before Bedrock usage starts** (GitHub Student Developer Pack, AWS Educate, or a university classroom grant) — this is what keeps the project at genuinely ~$0 out-of-pocket, and it's a week-1 task, not a semester-2 scramble.
- **Managed-service ceiling** — Lex/Contact Lens quality is what it is; if it under-performs on a needed scenario, that's a legitimate finding for the evaluation report, not a blocker to route around by rebuilding the stack.

---

## Verification

1. **Reproducibility:** a teammate outside the critical path deploys the Connect contact flow + Lambda stack from a clean AWS account and completes an answered call.
2. **Safety proof:** the red-team suite runs against the live number and prints an unauthorized-action count that must be 0; `verify_ledger.py` must exit 0.
3. **Cost proof:** the weekly AWS Cost Explorer report is attached to every milestone — no number in the final report should be a surprise.
4. **Metrics proof:** the eval harness regenerates every reported number from the frozen held-out scenario set.
