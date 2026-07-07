from bot.database.models.player_model import Player


def get_or_create_player(db, discord_id: int, username: str) -> Player:
    """
    gets or creates a player profile for the given discord_id
    """
    player = db.query(Player).filter_by(id=discord_id).first()

    if player is None:
        player = Player(id=discord_id, username=username)
        db.add(player)
        db.commit()
        db.refresh(player)

    return player


def get_player(db, discord_id: int) -> Player | None:
    """
    returns the player profile for the given discord_id, or None if they haven't started
    """
    return db.query(Player).filter_by(id=discord_id).first()
