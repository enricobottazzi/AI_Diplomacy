# NDAI Zone Protocol State Machine

## Intents

| Intent | Description |
|--------|-------------|
| **CONTINUE** | Regular message, no proposal action |
| **PROPOSE** | Propose a joint statement (must include `joint_statement`). A deliberate counter-proposal (in a later round, after seeing the other side's proposal) supersedes the reverse pending proposal. Concurrent cross-proposals (same round) both survive |
| **ACCEPT** | Accept the most recent proposal from the recipient |

## Processing Order Within a Round

All powers generate messages **concurrently** (via `asyncio.gather`). Messages from a single round cannot see each other. After collection, the state machine processes messages in **priority order**:

1. **ACCEPTs first** — An ACCEPT always beats a concurrent PROPOSE. If A sends ACCEPT and B sends PROPOSE in the same round, A's ACCEPT is processed first (agreement recorded), then B's PROPOSE creates a new pending proposal.
2. **PROPOSEs second** — When two powers send cross-proposals (A→B PROPOSE and B→A PROPOSE) in the **same round**, both proposals become pending simultaneously — neither agent saw the other's proposal, so there is no counter-proposal intent. In a **subsequent round**, a PROPOSE from B→A when `pending_proposals[(A,B)]` already exists is a deliberate counter-proposal and supersedes A's pending proposal.
3. **CONTINUEs last** — No state change, just stored.

All messages are stored in ephemeral history in their **original collection order** (by power), regardless of processing order.

## State Transitions

For a pair of powers **(A, B)**, the protocol tracks `pending_proposals[(X, Y)]` — meaning X has an active proposal to Y.

### When NO pending proposal exists between A and B

| A sends | B sends | Outcome |
|---------|---------|---------|
| CONTINUE | CONTINUE | No state change. Messages stored in ephemeral history |
| CONTINUE | PROPOSE | `pending_proposals[(B,A)]` created |
| CONTINUE | ACCEPT | B's ACCEPT ignored (warning: no pending proposal) |
| PROPOSE | CONTINUE | `pending_proposals[(A,B)]` created |
| PROPOSE | PROPOSE | Both created concurrently. Since neither agent saw the other's proposal, both become pending: `pending_proposals[(A,B)]` and `pending_proposals[(B,A)]`. In the next round, either side can ACCEPT the other's joint statement |
| PROPOSE | ACCEPT | ACCEPT processed first → ignored (no pending proposal). Then PROPOSE creates `pending_proposals[(A,B)]` or `(B,A)` |
| ACCEPT | CONTINUE | A's ACCEPT ignored (no pending proposal) |
| ACCEPT | PROPOSE | ACCEPT processed first → ignored. Then PROPOSE creates `pending_proposals[(B,A)]` |
| ACCEPT | ACCEPT | Both ACCEPTs ignored (no pending proposals) |

### When `pending_proposals[(A, B)]` exists (A proposed to B in a previous round)

| A sends | B sends | Outcome |
|---------|---------|---------|
| CONTINUE | CONTINUE | No change. A's proposal remains pending |
| CONTINUE | PROPOSE | B's PROPOSE triggers counter-proposal: clears `(A,B)`, creates `(B,A)`. Note added to message |
| CONTINUE | ACCEPT | **ACCEPT processed first.** B accepts A's proposal → agreement recorded. `(A,B)` removed |
| PROPOSE | CONTINUE | A sends new PROPOSE to B: overwrites `(A,B)` with new statement |
| PROPOSE | PROPOSE | B's PROPOSE is a deliberate counter-proposal (B saw A's pending proposal): clears `(A,B)`, creates `(B,A)`. A's new PROPOSE creates `(A,B)` again. Both survive as independent pending proposals |
| PROPOSE | ACCEPT | **ACCEPT processed first.** B accepts old `(A,B)` → agreement recorded. Then A's new PROPOSE creates `(A,B)` again as a fresh pending proposal |
| ACCEPT | CONTINUE | A's ACCEPT checks for `(B,A)` → not found → ignored. A's own proposal `(A,B)` unchanged |
| ACCEPT | PROPOSE | **ACCEPT processed first.** A's ACCEPT checks `(B,A)` → not found → ignored. Then B's PROPOSE is a deliberate counter-proposal: clears `(A,B)`, creates `(B,A)` |
| ACCEPT | ACCEPT | **ACCEPTs processed first.** B's ACCEPT finds `(A,B)` → agreement. A's ACCEPT checks `(B,A)` → not found → ignored |

### When both `pending_proposals[(A, B)]` and `pending_proposals[(B, A)]` exist (concurrent cross-proposals from a previous round)

| A sends | B sends | Outcome |
|---------|---------|---------|
| CONTINUE | CONTINUE | No change. Both proposals remain pending |
| CONTINUE | PROPOSE | B's new PROPOSE overwrites `(B,A)` with new text. A's `(A,B)` unchanged |
| CONTINUE | ACCEPT | **ACCEPT processed first.** B accepts A's proposal `(A,B)` → agreement recorded, `(A,B)` removed. B's own `(B,A)` remains pending |
| PROPOSE | CONTINUE | A's new PROPOSE overwrites `(A,B)` with new text. B's `(B,A)` unchanged |
| PROPOSE | PROPOSE | Both overwrite their own pending proposals with new text. `(A,B)` updated, `(B,A)` updated. Both remain pending |
| PROPOSE | ACCEPT | **ACCEPT processed first.** B accepts `(A,B)` → agreement recorded, `(A,B)` removed. Then A's PROPOSE creates fresh `(A,B)`. B's `(B,A)` unchanged |
| ACCEPT | CONTINUE | **ACCEPT processed first.** A accepts B's proposal `(B,A)` → agreement recorded, `(B,A)` removed. A's own `(A,B)` remains pending |
| ACCEPT | PROPOSE | **ACCEPT processed first.** A accepts `(B,A)` → agreement recorded, `(B,A)` removed. Then B's PROPOSE creates fresh `(B,A)`. A's `(A,B)` unchanged |
| ACCEPT | ACCEPT | **ACCEPTs processed first.** Both accept each other's proposals → **two agreements** recorded. Both `(A,B)` and `(B,A)` removed |

## Key Rules

1. **Concurrent messages cannot see each other.** Within a round, all powers generate simultaneously. They only see messages from previous rounds.

2. **ACCEPT is always privileged.** ACCEPTs are processed before PROPOSEs within a round, so a concurrent ACCEPT+PROPOSE always results in the agreement being recorded, plus the new PROPOSE stored.

3. **Concurrent cross-proposals both survive.** When two powers PROPOSE to each other in the **same round**, both proposals become pending — `pending_proposals[(A,B)]` and `pending_proposals[(B,A)]` coexist. Neither agent saw the other's proposal, so there is no counter-proposal intent. Both can be ACCEPTed in the next round, potentially yielding two agreements.

4. **Deliberate counter-proposal clears reverse.** When a PROPOSE from B→A arrives in a **subsequent round** (B has seen A's pending proposal in the ephemeral history), it is treated as a deliberate counter-proposal and clears `pending_proposals[(A,B)]`.

5. **Only PROPOSE+ACCEPT = joint statement.** A joint statement requires an explicit PROPOSE followed by an explicit ACCEPT (typically in a later round).

6. **Expired proposals are logged.** Any pending proposal still active when the zone exits is logged as a warning.

7. **Repetition guard.** If power A sent a message to power B in round *N* and B has not yet replied to A, A's message to B in round *N+1* is silently discarded before it reaches the state machine. This prevents a power from flooding a recipient without waiting for a response. The guard resets as soon as B sends any message to A.
