"""
Build every player-facing select against an oversized account.

    python -m tools.check_select_limits

THE BUG THIS EXISTS FOR
-----------------------
The equip-target picker listed EVERY character the player owns, unpaged.
Once the roster passed 25 Discord rejected the whole payload:

    400 Bad Request (error code: 50035): Invalid Form Body
    In data.components.0.components.0.options: Must be between 1 and 25

The edit raised, so the interaction was never answered, so the button
appeared to do nothing -- and the follow-on "interaction expired before
component could reply" warnings were the same click being retried
against a token nothing had replied to. Equipping was impossible for
precisely the players with the most characters to equip onto.

WHY THE EXISTING CHECKS MISSED IT
---------------------------------
`bot/utils/paging.py` was written for this exact failure and its
docstring lists the five menus fixed at the time. This one was not among
them, because it builds its options in a request handler rather than in
a view class -- so it did not look like the others, and nothing was
comparing it against the limit.

Every previous fix here has been "page the menu we just noticed". That
is a checklist, and checklists rot. This runs the constructors instead,
against a deliberately absurd account: 40 characters, 60 cards, 300
items. A menu that cannot survive that is a menu that will break for a
real player eventually, and this fails NOW rather than in their log.

BOTH BOUNDS MATTER. Discord's message is "between 1 and 25": an EMPTY
select is rejected just as hard as an overfull one, and empty is the
easier one to write by accident (filter a list, get nothing back).
"""

from __future__ import annotations

import random
import sys
import tempfile

LIMIT = 25
ROSTER_SIZE = 40
CARD_COUNT = 60
ITEM_COUNT = 300


def main() -> int:
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))

    import discord
    from sqlalchemy.orm import sessionmaker

    from bot.database.db import engine
    from bot.database.db_init import init_db
    from bot.database.models.character_model import CharacterTemplate
    from bot.database.models.enums import Rarity
    from bot.database.models.player_model import Player
    from bot.game.economy import card_config as cc
    from bot.game.loot.generator import LootGenerator
    from bot.services import (
        card_service, character_service, character_template_service,
        item_template_service, lootbox_service,
    )

    init_db()
    db = sessionmaker(bind=engine)()
    item_template_service.ensure_item_templates_seeded(db)
    lootbox_service.ensure_lootbox_templates_seeded(db)
    character_template_service.ensure_character_templates_seeded(db)
    card_service.ensure_card_templates_seeded(db)

    player = Player(id=1, username="limits", gold=10**9, echoes=10**9,
                    cores=10**9, evolution_fragments=10**6)
    db.add(player)
    db.commit()

    # --- an account bigger than anyone will realistically have ----------
    avatar = character_template_service.get_avatar_template(db)
    first, _, _ = character_service.grant_character(db, player, avatar)
    character_service.set_squad_slot(db, player, 0, first)
    templates = db.query(CharacterTemplate).filter_by(is_player_avatar=False).all()
    owned = [first]
    while len(owned) < ROSTER_SIZE:
        for template in templates:
            if len(owned) >= ROSTER_SIZE:
                break
            pc, _, _ = character_service.grant_character(db, player, template)
            owned.append(pc)
    db.commit()

    for index in range(CARD_COUNT):
        card_service.grant_card(db, player, cc.CARD_TEMPLATES[index % len(cc.CARD_TEMPLATES)]["id"])

    rng = random.Random(1)
    generator = LootGenerator(rng=rng)
    for _ in range(ITEM_COUNT):
        template = item_template_service.pick_random_template(db, rng=rng, rarity=Rarity.RARE)
        db.add(generator.generate_item(template, player_id=player.id,
                                       item_level=1, rarity_override=Rarity.RARE))
    db.commit()

    failures: list[str] = []
    checked = 0

    def inspect(label: str, view_or_select) -> None:
        """Every select on a built view must hold 1-25 options."""
        nonlocal checked
        items = (view_or_select.children
                 if isinstance(view_or_select, discord.ui.View) else [view_or_select])
        selects = [i for i in items if isinstance(i, discord.ui.Select)]
        if not selects:
            failures.append(f"{label}: rendered no select at all")
            return
        for select in selects:
            checked += 1
            count = len(select.options)
            if count > LIMIT:
                failures.append(
                    f"{label}: {count} options, over Discord's ceiling of {LIMIT} -- "
                    f"the whole payload is rejected with 'Invalid Form Body', the "
                    f"interaction is never answered, and the control appears dead"
                )
            elif count == 0:
                failures.append(
                    f"{label}: 0 options -- Discord requires between 1 and {LIMIT}, "
                    f"so an empty select fails exactly as hard as an overfull one"
                )

    # ---- the menus that list an unbounded, player-owned collection -----
    from bot.cogs.cards import CardCharacterSelect, CardSelect
    from bot.cogs.inventory import EquipTargetView
    from bot.cogs.squad import SquadView

    squad_ids = {pc.id for pc in character_service.get_squad(db, player)}
    from bot.database.models.equipment_model import InventoryItem
    any_item = db.query(InventoryItem).filter_by(player_id=player.id).first()

    inspect("inventory.EquipTargetView (page 0)",
            EquipTargetView(any_item.id, owned, squad_ids, owner_id=player.id))
    inspect("inventory.EquipTargetView (last page)",
            EquipTargetView(any_item.id, owned, squad_ids, owner_id=player.id, page=99))

    cards = card_service.list_cards(db, player.id)
    inspect("cards.CardSelect (page 0)", CardSelect(cards, {}, None, 0))
    inspect("cards.CardCharacterSelect (page 0)", CardCharacterSelect(cards[0].id, owned, 0))
    inspect("cards.CardCharacterSelect (last page)",
            CardCharacterSelect(cards[0].id, owned, 99))

    by_slot = {i: None for i in range(4)}
    by_slot[0] = first
    inspect("squad.SquadView (page 0)", SquadView(db, player, owned, by_slot))
    inspect("squad.SquadView (last page)", SquadView(db, player, owned, by_slot, page=99))

    # ...and the same menus with an EMPTY account, which is the other
    # half of "between 1 and 25" and the easier one to write by accident.
    inspect("cards.CardSelect (no cards)", CardSelect([], {}, None, 0))
    inspect("cards.CardCharacterSelect (no characters)", CardCharacterSelect(1, [], 0))

    # ---- the Echo Exchange, which lists two whole catalogs -------------
    from bot.cogs.economy import _render_exchange
    for counter in ("characters", "cards"):
        for page in (0, 99):
            _, view = _render_exchange(db, player, counter, page)
            inspect(f"economy exchange {counter} (page {page})", view)

    print(f"account  : {ROSTER_SIZE} characters, {CARD_COUNT} cards, {ITEM_COUNT} items")
    print(f"selects  : {checked} built and measured against the 1-{LIMIT} window")
    print()
    if failures:
        for line in dict.fromkeys(failures):
            print(f"  FAIL  {line}")
        return 1
    print("OK -- every menu fits, on the first page and the last.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(main())
