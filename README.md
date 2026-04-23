# Daily Thunder Decentralized Builder

This repo separates state refresh from post creation.

## Lanes
- `dt_state_updater.py` refreshes JSON only
- `dt_pregame.py` creates/updates Pregame Primer drafts
- `dt_scoreboard.py` creates one Thunder Scoreboard draft for the latest final
- `dt_dayafter.py` creates one Day After Report draft for the latest final
- `dt_podcast.py` creates one draft per new podcast episode
- `dt_bolts_intake.py` and `dt_bolts_roundup.py` are intentionally inactive scaffolds

## Required Secrets
- `GHOST_URL`
- `GHOST_ADMIN_KEY`

## Files
Shared JSON state:
- `season_config.json`
- `season_state.json`
- `series_config.json`
- `content_state.json`
- `team_state.json`
- `stats_state.json`

The workflows run independently so one broken Ghost payload cannot kill state updates or the other post lanes.
