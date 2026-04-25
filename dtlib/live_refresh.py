from __future__ import annotations

from typing import Any, Dict

from .espn_sources import refresh_game_espn_context, resolve_espn_event_id_for_game
from .injury_sources import refresh_game_injuries
from .starter_sources import refresh_game_starters


def refresh_game_live_fields(game: Dict[str, Any]) -> bool:
    changed = False

    try:
        event_id = resolve_espn_event_id_for_game(game)
        if event_id:
            print(f'Live refresh event resolved for {game.get("game_id")}: {event_id}')
    except Exception as exc:
        print(f'Live refresh event resolution failed for {game.get("game_id")}: {exc}')

    try:
        changed = refresh_game_espn_context(game) or changed
    except Exception as exc:
        print(f'Live refresh ESPN context failed for {game.get("game_id")}: {exc}')

    try:
        changed = refresh_game_injuries(game) or changed
    except Exception as exc:
        print(f'Live refresh injuries failed for {game.get("game_id")}: {exc}')

    try:
        changed = refresh_game_starters(game) or changed
    except Exception as exc:
        print(f'Live refresh starters failed for {game.get("game_id")}: {exc}')

    if changed:
        print(f'Live refresh changed fields for {game.get("game_id")}')
    else:
        print(f'Live refresh no meaningful changes for {game.get("game_id")}')
    return changed
