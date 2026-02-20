# NDAI Zone Protocol State Machine

## Intents

| Intent | Description |
|--------|-------------|
| **CONTINUE** | Regular message, no proposal action |
| **PROPOSE** | Propose a joint statement (must include `joint_statement`). Counter-proposing supersedes any reverse pending proposal |
| **ACCEPT** | Accept the most recent proposal from the recipient |

## Processing Order Within a Round

All powers generate messages **concurrently** (via `asyncio.gather`). Messages from a single round cannot see each other. After collection, the state machine processes messages in **priority order**:

1. **ACCEPTs first** — An ACCEPT always beats a concurrent PROPOSE. If A sends ACCEPT and B sends PROPOSE in the same round, A's ACCEPT is processed first (agreement recorded), then B's PROPOSE creates a new pending proposal.
2. **PROPOSEs second, in random order** — When two powers send cross-proposals (A→B PROPOSE and B→A PROPOSE), the processing order is randomized. The second-processed one triggers the counter-proposal rule and clears the first. Neither power has a deterministic advantage.
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
| PROPOSE | PROPOSE | Both created concurrently. Random coin flip determines which is processed first. The second-processed one clears the first (counter-proposal rule). Only one survives |
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
| PROPOSE | PROPOSE | Random order. One creates/overwrites, the other counter-proposes and clears. Only one survives |
| PROPOSE | ACCEPT | **ACCEPT processed first.** B accepts old `(A,B)` → agreement recorded. Then A's new PROPOSE creates `(A,B)` again as a fresh pending proposal |
| ACCEPT | CONTINUE | A's ACCEPT checks for `(B,A)` → not found → ignored. A's own proposal `(A,B)` unchanged |
| ACCEPT | PROPOSE | **ACCEPT processed first.** A's ACCEPT checks `(B,A)` → not found → ignored. Then B's PROPOSE clears `(A,B)` (counter-proposal), creates `(B,A)` |
| ACCEPT | ACCEPT | **ACCEPTs processed first.** B's ACCEPT finds `(A,B)` → agreement. A's ACCEPT checks `(B,A)` → not found → ignored |

## Key Rules

1. **Concurrent messages cannot see each other.** Within a round, all powers generate simultaneously. They only see messages from previous rounds.

2. **ACCEPT is always privileged.** ACCEPTs are processed before PROPOSEs within a round, so a concurrent ACCEPT+PROPOSE always results in the agreement being recorded, plus the new PROPOSE stored.

3. **Cross-proposals resolved randomly.** When two powers PROPOSE to each other in the same round, the winner is chosen by random shuffle — no power has a deterministic advantage.

4. **Counter-proposal clears reverse.** A PROPOSE from B→A always clears any existing `pending_proposals[(A,B)]` from the previous round.

5. **Only PROPOSE+ACCEPT = agreement.** An agreement requires an explicit PROPOSE followed by an explicit ACCEPT (typically in a later round).

6. **Expired proposals are logged.** Any pending proposal still active when the zone exits is logged as a warning.

7. **Repetition guard.** If power A sent a message to power B in round *N* and B has not yet replied to A, A's message to B in round *N+1* is silently discarded before it reaches the state machine. This prevents a power from flooding a recipient without waiting for a response. The guard resets as soon as B sends any message to A.
