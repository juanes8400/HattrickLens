# EXPERIENCE_ENGINE

# Experience Engine Specification

## Purpose

The Experience Engine estimates and tracks every player's progression toward the next Experience level. It reproduces the Hattrick experience system by converting official matches into experience points and calculating progress to the next level.

---

# Objectives

- Track experience progression for every player.
- Estimate percentage toward the next experience level.
- Record historical experience increases.
- Explain how experience is accumulated.
- Provide forecasts for future experience gains.

---

# Responsibilities

- Detect every official match played by a player.
- Assign experience points according to match type.
- Accumulate points since the last experience increase.
- Calculate progress percentage.
- Maintain immutable historical records.

---

# Consumed By

- Team Module
- Player Details
- Position Engine (Captain evaluation)
- Match Simulator
- AI Assistant

---

# Inputs

For every player:

- Current Experience Level
- Leadership
- Last Experience Increase Date
- Friendly Matches Played
- International Friendlies Played
- League Matches Played
- Qualification Matches Played
- Cup Matches Played

Only matches played **since the last experience increase** are considered.

---

# Experience Point System

One experience level requires:

**100 Experience Points**

2026-08-05: rescaled from the original 28/0.1/0.2/1.0/2.0/2.0 profile to
Hattrick's real point values, cross-checked against
`docs/reference/tabla_experiencia.html`. The old profile turned out to be
this same table divided by 3.5 in every shared category (league 3.5→1.0,
international friendly 0.7→0.2, cup/qualification 7.0→2.0, friendly
0.35→0.1) — same proportions, confirmed by the user to top out at 100
points per level in Hattrick's own units, not the derived 98 (28×3.5).

---

## Match Values

| Match Type | Experience Points | Verified against Hattrick Control |
|------------|------------------:|:----------------------------------|
| Friendly | 0.35 | yes |
| International Friendly | 0.7 | yes |
| League Match | 3.5 | yes |
| Qualification Match (promoción) | 7.0 | from spec |
| Cup Match (copa principal) | 7.0 | from spec |
| HT Masters | 17.5 | from spec |
| National-team friendly | 3.5 | from spec |
| Youth league | 3.5 | from spec |
| Youth friendly | 0.35 | from spec |

Real Hattrick also grants experience for secondary cup matches (1.75),
competitive national-team matches (World Cup, continental cups, Nations
Cup and their qualifiers/knockout rounds — 7 to 70 depending on stage) and
the Challenger League (7). CHPP's `MatchType` field cannot distinguish which
of those a competitive national-team match belongs to (one code, 10/11,
covers all of them), so Lens detects and counts these matches without
guessing a point value for them — see `player_history.py`'s
`unscored_national_matches`. Two signals feed that count:

- Any national-team match actually captured through `LastMatch`
  (`playerdetails.xml`), once its real type is known (see the foreign-match
  backfill note above).
- `Caps`/`CapsU20` (career totals, same file): a career-cap increase since
  the current level started that is NOT explained by any captured match
  proves a national match happened even when `LastMatch` never caught it
  (the club played again before the next sync and overwrote it).

2026-08-05, pedido explícitamente: every match — club or national — awards
points proportional to minutes played over 90, capped at 100% (playing 70
of 90 minutes earns 70/90 of that competition's points; 90 or more earns
the full value, never more). This applies uniformly because
`player_match_ratings` already stores `played_minutes` per match; nothing
new to fetch, only a weight instead of a flat per-match count.

---

# Calculation

Total Experience Points =

Friendly × 0.35

+ International Friendly × 0.7

+ League × 3.5

+ Qualification × 7

+ Cup × 7

+ Masters × 17.5

+ National-team friendly × 3.5

+ Youth league × 3.5

+ Youth friendly × 0.35

Each match's contribution is itself scaled by minutes played:

match points × min(minutes played / 90, 1)

Progress Percentage =

(Total Experience Points / 100) × 100

Maximum displayed progress:

100%

---

# Player Table

Columns

- Player Name
- Nationality
- Age
- Current Experience
- Leadership
- Last Experience Increase
- Friendly Matches
- International Friendlies
- League Matches
- Qualification Matches
- Cup Matches
- Total Experience Points
- Progress %
- Estimated Remaining Points

---

# Historical Tracking

Every experience increase is stored.

Fields:

- Player
- Previous Experience Level
- New Experience Level
- Date
- Total Matches
- Total Experience Points

Historical records are immutable.

---

# Business Rules

- Only matches after the last experience increase count.
- Experience points never decrease.
- Progress resets after an experience increase.
- Historical calculations are reproducible.
- Constants are configuration-driven.

---

# Outputs

For every player:

- Experience Points
- Progress %
- Remaining Points
- Match Breakdown
- Historical Timeline

---

# Integrations

Provides information to:

- Team Module
- Captain Recommendation
- Position Engine
- Tactical Reports
- AI Recommendation Engine

---

# Future Enhancements

- Estimated date of next experience increase.
- Experience gain projections.
- Match scheduling optimization.
- Captain development tracking.
- Experience heatmaps.

---

# Success Criteria

Managers should understand exactly how much experience each player has accumulated, how close they are to the next experience level, which matches contributed to that progress, and how experience impacts tactical decisions such as captain selection.
