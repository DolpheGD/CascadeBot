"""
Dispatch board UI.

Underscore-prefixed so bot/client.py's cog loader skips it -- this holds
views and embeds, not a cog. Same convention as _dojo_ui.py.

THE SCREEN ANSWERS THREE QUESTIONS IN THIS ORDER, because that is the
order a returning player asks them:

    1. is anything ready to collect?
    2. what is still out, and when is it back?
    3. what could I send next?

An earlier arrangement led with the board, which meant the first thing a
player saw after eight hours away was a list of new work rather than the
reward they came back for.
"""

from __future__ import annotations

import discord

from bot.game.economy import dispatch_config as dc
from bot.services import dispatch_service as D
from bot.utils import responses

DISPATCH_COLOR = discord.Color.from_rgb(198, 143, 62)

_CLASS_ICON = {
    "DPS": "⚔️", "SUPPORT_DPS": "🎯", "SUSTAIN": "✚",
    "AMPLIFIER": "◆", "TANK": "🛡️",
}


def _class_name(value) -> str:
    return getattr(value, "name", str(value))


def _prefers_line(contract: dict) -> str:
    """'⚔️ DPS · ◆ Amplifier' -- or a plain note when it wants nobody.

    Spelled out rather than shown as icons alone. The icons are a
    scanning aid for people who already know the classes; a player three
    hours into the game does not, and a row of coloured shapes teaches
    them nothing.
    """
    wanted = contract.get("prefers") or []
    if not wanted:
        return "*Anyone will do.*"
    parts = []
    for cls in wanted:
        name = _class_name(cls)
        parts.append(f"{_CLASS_ICON.get(name, '•')} {name.replace('_', ' ').title()}")
    return " · ".join(parts)


def _short_delta(delta) -> str:
    total = max(0, int(delta.total_seconds()))
    hours, rest = divmod(total, 3600)
    minutes = rest // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _reward_line(rewards: dict) -> str:
    from bot.services.currency_service import format_currency

    parts = []
    for key, amount in rewards.items():
        if key.startswith("_"):
            continue
        if key == "xp":
            parts.append(f"✨ {amount:,} XP")
        else:
            parts.append(format_currency(key, amount))
    return " · ".join(parts)


def board_embed(db, player) -> discord.Embed:
    used, total = D.slots(db, player)

    embed = discord.Embed(
        title="📋 Dispatch Board",
        description=(
            "Send characters you aren't fighting with on timed contracts. "
            "**They can't be used in your squad until they return.**"
        ),
        color=DISPATCH_COLOR,
    )

    if total <= 0:
        embed.description = (
            f"The Dispatch Board opens at **HQ level "
            f"{dc.DISPATCH_UNLOCK_HQ_LEVEL}**.\n"
            f"Upgrade your HQ with `/base hq`."
        )
        return embed

    # ---- 1. out and back ---------------------------------------------
    active = D.active_dispatches(db, player)
    if active:
        lines = []
        for row in active:
            contract = dc.contract(row.contract_id)
            name = contract["name"] if contract else row.contract_id
            crew = len(row.character_ids or [])
            if D.ready(row):
                lines.append(f"✅ **{name}** — ready to claim "
                             f"({crew} back, {row.fit}% payout)")
            else:
                lines.append(f"🕗 **{name}** — {_short_delta(D.remaining(row))} left "
                             f"({crew} away, {row.fit}% payout)")
        embed.add_field(name=f"Out now — {used}/{total} slots",
                        value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(name=f"Out now — 0/{total} slots",
                        value="*Nobody is on a contract.*", inline=False)

    # ---- 2. what could I send ----------------------------------------
    running = {r.contract_id for r in active}
    offers = [c for c in D.board(db, player) if c["id"] not in running]
    if used >= total:
        embed.add_field(
            name="Available work",
            value="*Every slot is in use. Claim a contract to free one up.*",
            inline=False)
    elif offers:
        for contract in offers[:4]:
            embed.add_field(
                name=f"{contract['name']} — {contract['party']} "
                     f"character{'s' if contract['party'] > 1 else ''}, "
                     f"{contract['hours']}h",
                value=(f"{contract['description']}\n"
                       f"**Wants:** {_prefers_line(contract)}\n"
                       f"**Pays:** {_reward_line(contract['rewards'])}")[:1024],
                inline=False)
    else:
        embed.add_field(name="Available work",
                        value="*The board is empty. Check back shortly.*",
                        inline=False)

    embed.set_footer(text=f"Board refreshes every {dc.BOARD_REFRESH_HOURS}h  ·  "
                          f"payout scales with how well the team fits the job")
    return embed


class _ContractSelect(discord.ui.Select):
    """Pick a contract to staff."""

    def __init__(self, contracts: list[dict]):
        options = [
            discord.SelectOption(
                label=f"{c['name']}"[:100],
                value=c["id"],
                description=(f"{c['party']} char · {c['hours']}h · "
                             f"{_reward_line(c['rewards'])}")[:100],
            )
            for c in contracts[:25]      # Select hard-caps at 25
        ]
        super().__init__(placeholder="Choose a contract…", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: DispatchView = self.view
        await view.show_crew_picker(interaction, self.values[0])


class _CrewSelect(discord.ui.Select):
    """Pick exactly the crew the contract asks for."""

    def __init__(self, contract: dict, available: list):
        self.contract = contract

        # THE 25-OPTION CEILING IS REAL AND THIS ROSTER CAN EXCEED IT.
        #
        # Sorted by level descending before truncating, so the characters
        # cut are the ones least likely to be wanted. Silently showing
        # an arbitrary 25 of 34 would look like missing characters.
        pool = sorted(available, key=lambda c: -(c.level or 1))[:25]
        options = [
            discord.SelectOption(
                label=f"{c.display_name}"[:100],
                value=str(c.id),
                description=(f"Lv{c.level} · {c.template.star_rating}★ · "
                             f"{_class_name(c.template.character_class).replace('_', ' ').title()}")[:100],
            )
            for c in pool
        ]
        need = contract["party"]
        super().__init__(
            placeholder=f"Choose exactly {need} character{'s' if need > 1 else ''}…",
            options=options, min_values=need, max_values=need)

    async def callback(self, interaction: discord.Interaction):
        view: DispatchView = self.view
        await view.confirm_send(interaction, self.contract["id"],
                                [int(v) for v in self.values])


class DispatchView(discord.ui.View):
    def __init__(self, player_id: int, user_id: int):
        super().__init__(timeout=180)
        self.player_id = player_id
        self.user_id = user_id
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from bot.utils.ui_guard import check_owner
        return await check_owner(interaction, self.user_id)

    # ---- layout -------------------------------------------------------
    def _build(self):
        from bot.database.session import SessionLocal
        from bot.services.player_service import get_player

        self.clear_items()
        db = SessionLocal()
        try:
            player = get_player(db, self.user_id)
            if player is None:
                return
            used, total = D.slots(db, player)
            if total <= 0:
                return

            active = D.active_dispatches(db, player)
            claimable = [r for r in active if D.ready(r)]

            for row in claimable[:4]:
                contract = dc.contract(row.contract_id)
                label = f"Claim {contract['name'] if contract else 'contract'}"
                self.add_item(_ClaimButton(row.id, label[:80]))

            running = {r.contract_id for r in active}
            offers = [c for c in D.board(db, player) if c["id"] not in running]
            if used < total and offers:
                self.add_item(_ContractSelect(offers))
        finally:
            db.close()

    async def refresh(self, interaction: discord.Interaction, note: str | None = None):
        from bot.database.session import SessionLocal
        from bot.services.player_service import get_player

        self._build()
        db = SessionLocal()
        try:
            player = get_player(db, self.user_id)
            embed = board_embed(db, player)
        finally:
            db.close()
        if note:
            embed.add_field(name="​", value=note[:1024], inline=False)
        await responses.edit(interaction, embed=embed, view=self)

    # ---- flow ---------------------------------------------------------
    async def show_crew_picker(self, interaction: discord.Interaction, contract_id: str):
        from bot.database.models.character_model import PlayerCharacter
        from bot.database.session import SessionLocal
        from bot.services.player_service import get_player

        contract = dc.contract(contract_id)
        if contract is None:
            await responses.send(interaction, 
                "That contract is no longer on the board.", ephemeral=True)
            return

        db = SessionLocal()
        try:
            player = get_player(db, self.user_id)
            busy = D.busy_character_ids(db, player)
            available = [c for c in db.query(PlayerCharacter)
                         .filter_by(player_id=player.id).all()
                         if c.id not in busy]
        finally:
            db.close()

        if len(available) < contract["party"]:
            await responses.send(interaction, 
                f"**{contract['name']}** needs {contract['party']} character(s) "
                f"and you only have {len(available)} free. Claim a contract or "
                f"pull more characters first.", ephemeral=True)
            return

        self.clear_items()
        self.add_item(_CrewSelect(contract, available))
        self.add_item(_BackButton())
        embed = discord.Embed(
            title=f"📋 {contract['name']}",
            description=(f"{contract['description']}\n\n"
                         f"**Wants:** {_prefers_line(contract)}\n"
                         f"**Pays:** {_reward_line(contract['rewards'])}\n"
                         f"**Away for:** {contract['hours']}h"),
            color=DISPATCH_COLOR)
        embed.set_footer(text="Matching the classes it wants raises the payout.")
        await responses.edit(interaction, embed=embed, view=self)

    async def confirm_send(self, interaction: discord.Interaction,
                           contract_id: str, character_ids: list[int]):
        from bot.database.session import SessionLocal
        from bot.services.player_service import get_player

        db = SessionLocal()
        try:
            player = get_player(db, self.user_id)
            row, error = D.send(db, player, contract_id, character_ids)
            if row is None:
                await responses.send(interaction, error, ephemeral=True)
                return
            contract = dc.contract(contract_id)
            note = (f"**{contract['name']}** — sent. Back in "
                    f"{contract['hours']}h at **{row.fit}%** payout.")
        finally:
            db.close()
        await self.refresh(interaction, note)


class _ClaimButton(discord.ui.Button):
    def __init__(self, dispatch_id: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.success, emoji="✅")
        self.dispatch_id = dispatch_id

    async def callback(self, interaction: discord.Interaction):
        from bot.database.session import SessionLocal
        from bot.services.player_service import get_player

        view: DispatchView = self.view
        db = SessionLocal()
        try:
            player = get_player(db, view.user_id)
            rewards, error = D.claim(db, player, self.dispatch_id)
            if error:
                await responses.send(interaction, error, ephemeral=True)
                return
            levelled = rewards.pop("_levelled", [])
            note = f"**Collected:** {_reward_line(rewards)}"
            if levelled:
                note += "\n" + "\n".join(
                    f"⬆️ **{entry['name']}** {entry['from']} → {entry['to']}"
                    for entry in levelled)
        finally:
            db.close()
        await view.refresh(interaction, note)


class _BackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: DispatchView = self.view
        await view.refresh(interaction)
