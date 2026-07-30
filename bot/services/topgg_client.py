"""
Thin async client for the two top.gg endpoints /vote needs. Deliberately
hand-rolled on aiohttp (already a discord.py dependency) rather than
pulling in the topggpy SDK: we use two read-only GETs, and topggpy's
release history has repeatedly broken against new discord.py versions.

    has_voted(bot_id, user_id) -> bool
        "Did this user vote for us within top.gg's 12h window?"
    is_weekend() -> bool
        Whether top.gg's double-vote weekend multiplier is running.

WHY POLLING RATHER THAN WEBHOOKS. Top.gg can push a POST to a URL of your
choice the instant someone votes, which is the lower-latency option -- but
it requires a publicly reachable HTTPS endpoint, which a bot run from a
home machine doesn't have. Polling on demand needs nothing but the token,
so /vote works the moment TOPGG_TOKEN is filled in. The trade-off is that
top.gg's check endpoint answers only "voted in the last 12h", with no
identity for *which* vote -- so it cannot tell us whether we've already
paid out for it. Player.last_vote_claimed_at is what prevents
double-claiming; see vote_service.claim_vote.

RESPONSE SHAPES. Top.gg is mid-migration from the v0 API to v1 and the
check endpoint has been documented with several different response bodies
over the years. Rather than pin to one and break on their next change,
_parse_voted below accepts every shape we've seen:

    {"voted": 1}                                  v0, the long-standing one
    {"voted": true}                               same, bool flavour
    {"user": "123", "timeLeft": 39600000, ...}    newer, present == voted
    {"user": false}                               newer, "hasn't voted"
    {"data": {...}}                               v1 envelope, unwrapped first

Anything genuinely unrecognised is treated as "not voted" and logged, so a
top.gg format change degrades into "the bot says you haven't voted yet"
rather than a crash or -- much worse -- free rewards for everyone.
"""

from __future__ import annotations

import aiohttp

from bot.config import TOPGG_TOKEN
from bot.utils.logger import get_logger

logger = get_logger("topgg")

API_BASE = "https://top.gg/api"
REQUEST_TIMEOUT_SECONDS = 8

# The page a player is sent to in order to vote. bot_id is the top.gg
# listing id, which for a normal listing is the bot's own application id.
VOTE_URL_TEMPLATE = "https://top.gg/bot/{bot_id}/vote"


class TopGGError(Exception):
    """Any failure talking to top.gg -- network, timeout, auth, or a
    non-200 status. The message is written to be shown to the player, so
    callers can surface it directly instead of translating it."""


def is_configured() -> bool:
    """False when TOPGG_TOKEN isn't set, in which case /vote should
    explain that voting isn't set up rather than attempt a call."""
    return bool(TOPGG_TOKEN)


def vote_url(bot_id: int) -> str:
    return VOTE_URL_TEMPLATE.format(bot_id=bot_id)


def _headers() -> dict[str, str]:
    # v0 endpoints take the bare token; v1 requires a "Bearer " prefix and
    # rejects the bare form. We're on v0 paths here, so send it bare.
    return {"Authorization": TOPGG_TOKEN or "", "Accept": "application/json"}


async def _get(path: str, params: dict | None = None) -> dict:
    if not is_configured():
        raise TopGGError("Voting isn't set up on this bot yet.")

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{API_BASE}{path}", params=params, headers=_headers()) as resp:
                if resp.status == 401:
                    logger.error("top.gg rejected our token (401) on %s", path)
                    raise TopGGError(
                        "This bot's top.gg token is invalid or expired -- "
                        "let the bot owner know."
                    )
                if resp.status == 404:
                    logger.error("top.gg returned 404 on %s -- is the bot listed?", path)
                    raise TopGGError(
                        "This bot doesn't seem to be listed on top.gg yet."
                    )
                if resp.status == 429:
                    raise TopGGError("Top.gg is rate-limiting us right now -- try again shortly.")
                if resp.status >= 400:
                    logger.error("top.gg returned %s on %s", resp.status, path)
                    raise TopGGError("Top.gg returned an error -- try again in a minute.")
                return await resp.json(content_type=None)
    except TopGGError:
        raise
    except aiohttp.ClientError as exc:
        logger.warning("top.gg request to %s failed: %s", path, exc)
        raise TopGGError("Couldn't reach top.gg right now -- try again in a minute.") from exc
    except TimeoutError as exc:
        logger.warning("top.gg request to %s timed out", path)
        raise TopGGError("Top.gg took too long to respond -- try again in a minute.") from exc


def _parse_voted(payload: dict) -> bool:
    """Normalizes top.gg's several documented check-response shapes into a
    single bool. See the module docstring for the shapes handled. Unknown
    payloads deliberately return False (never a free reward)."""
    if not isinstance(payload, dict):
        logger.warning("top.gg check returned a non-object payload: %r", payload)
        return False

    # v1 wraps its result in a "data" envelope; unwrap once if present.
    if isinstance(payload.get("data"), dict):
        payload = payload["data"]

    if "voted" in payload:
        return bool(payload["voted"])

    if "user" in payload:
        # Newer shape: a user object (or id) means they voted; literal
        # false means they didn't.
        return bool(payload["user"])

    if "hasVoted" in payload:
        return bool(payload["hasVoted"])

    logger.warning("Unrecognised top.gg check response: %r", payload)
    return False


async def has_voted(bot_id: int, user_id: int) -> bool:
    """Whether `user_id` has voted for `bot_id` inside top.gg's current
    12-hour window. Raises TopGGError with a player-facing message on any
    failure -- never silently returns False for a transport problem, since
    that would read to the player as "your vote didn't count"."""
    payload = await _get(f"/bots/{bot_id}/check", params={"userId": str(user_id)})
    return _parse_voted(payload)


async def is_weekend() -> bool:
    """Whether top.gg's double-vote weekend is currently running. Best
    effort: a failure here downgrades the reward rather than blocking the
    claim, so this swallows TopGGError and returns False."""
    try:
        payload = await _get("/weekend")
    except TopGGError:
        return False
    if isinstance(payload.get("data"), dict):
        payload = payload["data"]
    return bool(payload.get("is_weekend") or payload.get("isWeekend"))
