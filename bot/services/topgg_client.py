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
    {"created_at": ..., "expires_at": ...}        v1 vote record; expires_at
                                                  is honoured, so a LAPSED
                                                  vote reads as not voted

Anything genuinely unrecognised is treated as "not voted" and logged, so a
top.gg format change degrades into "the bot says you haven't voted yet"
rather than a crash or -- much worse -- free rewards for everyone.

404 MEANS "NO VOTE RECORD", NOT "NO BOT". The check endpoint looks up a
user's VOTE, so a user who hasn't voted (or whose 12h window lapsed) gets
a 404, not a 200 saying "voted: 0". This is much clearer in the v1
successor -- `GET /v1/projects/@me/votes/:user_id`, which returns that
vote's created_at/expires_at and has nothing to return when there isn't
one. has_voted therefore treats a 404 as "hasn't voted" and only reports
a missing LISTING after separately confirming the listing is missing.

ON MIGRATING TO v1. The v1 endpoint is better for us -- it returns
`expires_at`, which would remove the guesswork this module documents
below about not knowing WHICH vote we're seeing. It's deliberately not
used yet for one reason: v1 rejects legacy tokens outright and needs a
newly-generated one, so switching would silently break voting for any
deployment still holding an old token. Worth doing behind a config flag
once a new token is in place.
"""

from __future__ import annotations

import datetime as dt

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


class TopGGNotFound(TopGGError):
    """A 404 from top.gg.

    Its own type because 404 is the one status whose MEANING depends
    entirely on which endpoint returned it -- see has_voted, which treats
    a 404 from the per-user check as "hasn't voted" rather than as a
    failure. Every other caller can keep catching plain TopGGError."""


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
                    # Deliberately NOT logged as an error here. A 404's
                    # meaning depends on the endpoint, and the caller is
                    # the only thing that knows which one it asked -- see
                    # has_voted. Logging "is the bot listed?" from this
                    # level is what made a routine per-user 404 look like
                    # a broken listing for months.
                    body = (await resp.text())[:200]
                    logger.debug("top.gg 404 on %s params=%s body=%r", path, params, body)
                    raise TopGGNotFound("top.gg has no record at that path.")
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


async def _listing_exists(bot_id: int) -> bool:
    """Whether top.gg actually has a listing for `bot_id`.

    Only called on the 404 path, to tell the two very different causes
    apart: a missing LISTING (a config problem the owner must fix, and
    which would 404 for everybody) versus a missing VOTE RECORD for one
    user (routine). Without this the two are indistinguishable, because
    top.gg answers both with a bare 404."""
    try:
        await _get(f"/bots/{bot_id}")
        return True
    except TopGGNotFound:
        return False
    except TopGGError:
        # Any other failure (rate limit, network) tells us nothing about
        # the listing. Assume it exists -- the alternative is telling the
        # owner their bot is unlisted because top.gg rate-limited us.
        return True


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

    # The v1 VOTE RECORD shape: {created_at, expires_at, weight}. Handled
    # here even though we call a v0 path, because top.gg is mid-migration
    # and has changed this endpoint's body before -- if the legacy path
    # starts answering in the new shape, the alternative is every vote
    # silently failing to register for every player at once, with nothing
    # in the logs but "Unrecognised".
    #
    # expires_at is honoured rather than assumed: a record exists for a
    # LAPSED vote too, and treating that as a live vote would hand out a
    # reward for a vote that expired.
    if "expires_at" in payload or "created_at" in payload:
        expires_at = payload.get("expires_at")
        if not expires_at:
            return True
        try:
            expiry = dt.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=dt.timezone.utc)
            return expiry > dt.datetime.now(dt.timezone.utc)
        except ValueError:
            logger.warning("top.gg sent an unparseable expires_at: %r", expires_at)
            return True

    logger.warning("Unrecognised top.gg check response: %r", payload)
    return False


async def has_voted(bot_id: int, user_id: int) -> bool:
    """Whether `user_id` has voted for `bot_id` inside top.gg's current
    12-hour window. Raises TopGGError with a player-facing message on a
    transport failure -- never silently returns False for one, since that
    would read to the player as "your vote didn't count".

    A 404 IS NOT A FAILURE HERE. Top.gg's vote check is a lookup of a
    VOTE RECORD, not of the bot: its v1 successor is literally
    `GET /v1/projects/@me/votes/:user_id` returning that vote's
    created_at/expires_at, and a user with no current vote has no record
    to return. So a user who has never voted -- or whose 12h window has
    lapsed -- 404s, while a user who has voted gets a 200.

    That's why the symptom looked so strange: the error appeared for
    SOME users while voting demonstrably worked for others, on a bot that
    was listed the whole time. This function used to turn that routine
    "no vote yet" into a hard error reading "This bot doesn't seem to be
    listed on top.gg yet", which is both wrong and the single most
    misleading thing it could have said -- it sent the owner to check a
    listing that was never the problem.

    The genuinely-unlisted case still needs reporting, since it looks
    identical from a single response, so it's disambiguated with one
    extra request on the 404 path only."""
    try:
        payload = await _get(f"/bots/{bot_id}/check", params={"userId": str(user_id)})
    except TopGGNotFound:
        if await _listing_exists(bot_id):
            logger.info(
                "top.gg has no current vote record for user %s -- treating as 'not voted'",
                user_id,
            )
            return False
        logger.error(
            "top.gg has no listing for bot %s -- /vote cannot work until it's listed", bot_id
        )
        raise TopGGError("This bot doesn't seem to be listed on top.gg yet.") from None
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
