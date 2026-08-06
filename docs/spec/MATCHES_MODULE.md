# MATCHES_MODULE

# Matches Module Specification

## Purpose

The Matches module is the tactical analysis center of HT Lens. It provides a complete historical record of every match played by the club and transforms match data into actionable insights through visualizations, statistics and comparative analysis.

---

# Objectives

- Store every official and friendly match.
- Display historical ratings.
- Analyze tactical strengths and weaknesses.
- Visualize match events.
- Compare performance across time.
- Support future simulation and AI modules.

---

# Functional Tabs

1. Match List
2. Lineup
3. Ratings
4. Events
5. Summary
6. Charts
7. Statistics
8. Event Summary

---

# Match List

Displays every synchronized match.

Default order:

- Most recent first.

Filters:

- Competition
- Season
- Date range
- Home/Away
- Opponent

Columns:

- Date
- Competition
- Opponent
- Home/Away
- Result
- Formation
- Tactic
- Stars
- HatStats

Selecting a match updates every other tab.

---

# Lineup

Displays the starting lineup.

Features:

- Player positions
- Formation
- Minute-by-minute positional changes
- Substitutions
- Injuries
- Red cards

Future:

Animated tactical replay.

---

# Ratings

Compares both teams.

Metrics:

- Stars
- HatStats
- Midfield
- Right Defense vs Left Attack
- Central Defense vs Central Attack
- Left Defense vs Right Attack
- Right Attack vs Left Defense
- Central Attack vs Central Defense
- Left Attack vs Right Defense

Visual representation should resemble the official Hattrick match viewer.

---

# Events

Chronological event list.

Categories:

- Chances
- Goals
- Information
- Cards
- Injuries
- Special Events

Each event includes:

- Minute
- Team
- Player(s)
- Event type
- Event description

---

# Summary

Historical table with filters.

Competition filters:

- League
- Cup
- Friendly

Date filters:

- Start date
- End date

Columns:

- Date
- Match
- Result
- Tactic
- HatStats
- Stars
- PIC/Normal/MOTS
- Midfield
- Right Defense
- Central Defense
- Left Defense
- Right Attack
- Central Attack
- Left Attack
- HT Week

---

# Charts

Interactive charts.

Selectable metrics:

- HatStats
- Stars
- Midfield
- Right Defense
- Central Defense
- Left Defense
- Right Attack
- Central Attack
- Left Attack
- Indirect Free Kick Attack
- Indirect Free Kick Defense

Features:

- Multi-series line chart
- Competition filters
- Date filters
- Zoom
- Tooltips

---

# Statistics

Filters:

- Competition
- Date range
- Home
- Away

Displays:

## Match Results

- Wins
- Draws
- Losses
- Goals For
- Goals Against

Split by:

- Overall
- Home
- Away

## Best Historical Ratings

For every rating:

- Best value
- Date
- Opponent
- Result

Includes:

- HatStats
- Stars
- Midfield
- All defensive sectors
- All attacking sectors

---

# Event Summary

Aggregates all match events.

Filters:

- League
- Cup
- Friendly
- Date range

Breakdown for both teams.

Categories:

## Normal Chances

- Central
- Right
- Left
- Penalty
- Indirect Free Kick

## Special Events

- Corner
- Quick
- Technical vs Head
- Unpredictable
- Experience
- Winger
- Other

## Counterattacks

- Central
- Right
- Left
- Free Kick

Visualizations:

- Pie charts
- Bar charts
- Success percentages
- Chances vs Goals
- Team comparison

---

# Match Comparator Integration

Every match can be compared against any other historical match.

Comparison includes:

- Ratings
- HatStats
- Stars
- Tactical sectors

Future:

Monte Carlo simulation based on ratings.

---

# Business Rules

- Matches are immutable after synchronization.
- Derived statistics are recalculated automatically.
- Historical performance is never deleted.
- Charts are generated from historical records.
- Every visualization is filter-aware.

---

# Future Enhancements

- xG approximation
- Tactical heat maps
- Possession timeline
- Match simulator
- AI tactical report
- Opponent scouting
- Formation comparison
- Seasonal trend analysis

---

# Success Criteria

A manager should be able to understand why a match was won or lost, identify tactical patterns over time, evaluate strengths and weaknesses, and prepare future matches using historical evidence without leaving the Matches module.
