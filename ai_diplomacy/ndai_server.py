"""
NDAI zone negotiation server.

Runs inside the TEE. All messages are discarded on exit except
PROPOSE+ACCEPT pacts.
"""

import asyncio
import copy
import logging
from typing import Dict, List, Tuple, TYPE_CHECKING

from .utils import gather_possible_orders, normalize_recipient_name

if TYPE_CHECKING:
    from .game_history import GameHistory
    from .agent import DiplomacyAgent
    from diplomacy import Game

logger = logging.getLogger("ndai_server")


def _bump_error(model_error_stats, model_name, power_name):
    bucket = model_error_stats.setdefault(
        model_name if model_name in model_error_stats else power_name, {}
    )
    bucket["conversation_errors"] = bucket.get("conversation_errors", 0) + 1


async def run_ndai_negotiations(
    game: "Game",
    agents: Dict[str, "DiplomacyAgent"],
    game_history: "GameHistory",
    model_error_stats: Dict[str, Dict[str, int]],
    log_file_path: str,
    max_rounds: int = 3,
) -> Dict[Tuple[str, str], str]:
    """
    Run NDAI zone negotiations.  Returns agreed (proposer, accepter) -> text.
    """
    phase = game.current_short_phase
    active_powers = [p for p, obj in game.powers.items() if not obj.is_eliminated()]

    logger.info(f"[NDAI] Starting phase {phase} | powers={active_powers} | rounds={max_rounds}")

    ephemeral_history = copy.deepcopy(game_history)
    pending_proposals: Dict[Tuple[str, str], str] = {}
    proposal_round: Dict[Tuple[str, str], int] = {}
    agreed_statements: Dict[Tuple[str, str], str] = {}
    last_sent_round: Dict[Tuple[str, str], int] = {}
    awaiting_reply: Dict[Tuple[str, str], bool] = {}

    for rnd in range(max_rounds):
        logger.info(f"[NDAI] ─── Round {rnd + 1}/{max_rounds} ───")

        # ── Concurrent LLM calls ──
        tasks, task_powers = [], []
        for pname in active_powers:
            if pname not in agents:
                continue
            agent = agents[pname]
            possible_orders = gather_possible_orders(game, pname)
            if not possible_orders:
                continue
            tasks.append(
                agent.client.get_conversation_reply(
                    game, game.get_state(), pname, possible_orders,
                    ephemeral_history, phase,
                    log_file_path=log_file_path,
                    active_powers=active_powers,
                    agent_goals=agent.goals,
                    agent_relationships=agent.relationships,
                    agent_private_diary_str=agent.format_private_diary_for_prompt(),
                    negotiation_round=rnd + 1,
                    max_negotiation_rounds=max_rounds,
                    ndai=True,
                )
            )
            task_powers.append(pname)

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

        # ── Collect & validate ──
        round_msgs: List[Dict] = []
        for i, result in enumerate(results):
            pname = task_powers[i]
            model = agents[pname].client.model_name

            if isinstance(result, (Exception, type(None))):
                logger.warning(f"[NDAI] {pname}: LLM error/None ({result})")
                _bump_error(model_error_stats, model, pname)
                continue

            for msg in (result or []):
                if not isinstance(msg, dict) or "content" not in msg:
                    continue
                if msg.get("message_type") != "private":
                    continue
                recipient = normalize_recipient_name(msg.get("recipient", ""))
                if not recipient or recipient not in game.powers or recipient == pname:
                    continue

                pair = (pname, recipient)
                # Repetition guard: skip if we sent last round and got no reply
                if awaiting_reply.get(pair) and last_sent_round.get(pair) == rnd - 1:
                    logger.debug(f"[NDAI] {pname}->{recipient}: repetition guard, skipped")
                    continue

                last_sent_round[pair] = rnd
                awaiting_reply[pair] = True
                awaiting_reply[(recipient, pname)] = False

                intent = msg.get("intent", "CONTINUE").upper()
                js = msg.get("pact", "") or msg.get("deal", "")
                if intent not in ("CONTINUE", "PROPOSE", "ACCEPT"):
                    intent = "CONTINUE"
                if intent == "PROPOSE" and not js:
                    intent = "CONTINUE"

                round_msgs.append({
                    "pn": pname, "rec": recipient, "intent": intent,
                    "content": msg.get("content", ""), "js": js, "display": "",
                })

        # ── State machine: ACCEPTs first ──
        for m in round_msgs:
            if m["intent"] != "ACCEPT":
                continue
            m["display"] = f"[Intent: ACCEPT] {m['content']}"
            rev = (m["rec"], m["pn"])
            if rev in pending_proposals:
                stmt = pending_proposals.pop(rev)
                proposal_round.pop(rev, None)
                agreed_statements[rev] = stmt
                m["display"] += f"\n[Accepted Pact: {stmt[:120]}]"
                logger.info(f"[NDAI] AGREEMENT: {m['pn']} accepts {m['rec']}'s proposal")
            else:
                m["display"] += f"\n[Note: ACCEPT ignored — no pending proposal from {m['rec']}]"

        # ── PROPOSEs second ──
        for m in round_msgs:
            if m["intent"] != "PROPOSE":
                continue
            m["display"] = f"[Intent: PROPOSE] {m['content']}"
            fwd = (m["pn"], m["rec"])
            rev = (m["rec"], m["pn"])
            if rev in pending_proposals and proposal_round.get(rev) < rnd:
                # Deliberate counter-proposal: reverse was from a previous
                # round, so this agent saw it and chose to counter.
                old = pending_proposals.pop(rev)
                proposal_round.pop(rev, None)
                m["display"] += f"\n[Proposed Pact: {m['js']}]"
                m["display"] += f"\n[Note: Supersedes {m['rec']}'s proposal: {old[:80]}...]"
            else:
                # No reverse pending, or reverse is from the same round
                # (concurrent cross-proposal — both survive).
                m["display"] += f"\n[Proposed Pact: {m['js']}]"
            pending_proposals[fwd] = m["js"]
            proposal_round[fwd] = rnd
            logger.info(f"[NDAI] PROPOSE: {m['pn']}->{m['rec']}: {m['js'][:100]}")

        # ── CONTINUEs last ──
        for m in round_msgs:
            if m["intent"] == "CONTINUE":
                m["display"] = f"[Intent: CONTINUE] {m['content']}"

        # ── Store in ephemeral history (original order) ──
        for m in round_msgs:
            ephemeral_history.add_message(phase, m["pn"], m["rec"], m["display"])

        logger.info(
            f"[NDAI] Round {rnd + 1}: {len(round_msgs)} msgs | "
            f"pending={list(pending_proposals.keys())} | agreed={list(agreed_statements.keys())}"
        )

    # ── Final summary ──
    logger.info(f"[NDAI] Done phase {phase} | {len(agreed_statements)} pact(s)")
    for (proposer, accepter), stmt in agreed_statements.items():
        logger.info(f"[NDAI]   {proposer}<->{accepter}: {stmt[:150]}")
    for (proposer, recipient), stmt in pending_proposals.items():
        logger.warning(f"[NDAI]   Expired: {proposer}->{recipient}: {stmt[:150]}")

    return agreed_statements
