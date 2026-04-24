import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

SEED_PATH = Path("registry_seed_2025_26.json")
STATE_PATH = Path("season_state.json")

PRESERVE_GAME_KEYS = ("library", "assets", "automation", "timestamps")
PRESERVE_LIBRARY_KEYS = (
    "okc_injuries",
    "opp_injuries",
    "okc_likely_starters",
    "opp_likely_starters",
    "line",
    "feature_image_src",
    "feature_image_srcset",
    "matchup_matrix_src",
    "matchup_matrix_srcset",
)
PRESERVE_ASSET_KEYS = ("game_image_status", "scoreboard_image")
PRESERVE_AUTOMATION_KEYS = (
    "pregame_slug",
    "scoreboard_slug",
    "dayafter_slug",
    "pregame_complete",
    "scoreboard_complete",
    "dayafter_complete",
)


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def keyed_games(games: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(g.get("game_id")): g for g in games if g.get("game_id")}


def merge_game(seed: Dict[str, Any], existing: Dict[str, Any] | None) -> Dict[str, Any]:
    if not existing:
        return copy.deepcopy(seed)

    merged = copy.deepcopy(seed)

    for key in PRESERVE_GAME_KEYS:
        if isinstance(existing.get(key), dict):
            merged.setdefault(key, {})
            for sub_key, value in existing[key].items():
                if value not in (None, "", [], {}):
                    merged[key].setdefault(sub_key, value)

    for key in PRESERVE_LIBRARY_KEYS:
        value = existing.get("library", {}).get(key)
        if value not in (None, "", [], {}):
            merged.setdefault("library", {})[key] = value

    for key in PRESERVE_ASSET_KEYS:
        value = existing.get("assets", {}).get(key)
        if value not in (None, "", [], {}):
            merged.setdefault("assets", {})[key] = value

    for key in PRESERVE_AUTOMATION_KEYS:
        value = existing.get("automation", {}).get(key)
        if value not in (None, "", [], {}):
            merged.setdefault("automation", {})[key] = value

    return merged


def build_registry(seed_state: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
    current_by_id = keyed_games(current_state.get("games", []))
    out = copy.deepcopy(seed_state)
    out["games"] = [merge_game(seed_game, current_by_id.get(str(seed_game.get("game_id")))) for seed_game in seed_state.get("games", [])]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=str(SEED_PATH))
    parser.add_argument("--state", default=str(STATE_PATH))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    seed_path = Path(args.seed)
    state_path = Path(args.state)

    seed_state = load_json(seed_path, {"games": []})
    current_state = load_json(state_path, {"games": []})
    new_state = build_registry(seed_state, current_state)

    print(f"seed_games={len(seed_state.get('games', []))}")
    print(f"current_games={len(current_state.get('games', []))}")
    print(f"output_games={len(new_state.get('games', []))}")

    if args.write:
        state_path.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {state_path}")
    else:
        print("dry run only; pass --write to update season_state.json")


if __name__ == "__main__":
    main()
