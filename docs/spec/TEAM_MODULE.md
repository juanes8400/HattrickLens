# TEAM_MODULE

# Team Module Specification

## Purpose

The Team module is the operational center of HT Lens. It provides a complete view of the club's first-team squad, enabling managers to analyze players, evaluate positions, monitor development, and prepare tactical decisions.

---

# Objectives

- Display complete squad information.
- Evaluate every player's optimal position.
- Track player evolution.
- Monitor training and experience.
- Maintain historical player data.
- Support future lineup optimization.

---

# Functional Tabs

1. Players
2. Details
3. Positions
4. TSI History
5. Purchases & Sales
6. Next Match

---

# Players

## Description

Main table showing the complete squad.

### Columns

- Player Name
- Player ID
- Nationality (flag)
- Age
- Specialty
- Best Position
- Played This Week
- Transfer Listed
- Last Match Position
- Stars
- Form
- Experience
- Stamina
- Winger
- Scoring
- Goalkeeping
- Passing
- Defending
- Set Pieces
- Loyalty
- Mother Club
- TSI
- TSI Change
- Salary
- Purchase Price
- Character
- Aggressiveness
- Honesty
- Leadership
- Coach Status
- Coach Type
- League Goals
- Cup Goals
- Friendly Goals
- Career Goals
- Career Hat-tricks

Users may configure visible columns.

Sorting, filtering and searching are available on every column.

---

# Player Details

Displays a complete player profile.

Includes:

- Personal information
- Skill breakdown
- Current training
- Estimated training progress
- Experience progress
- Historical TSI
- Historical skills
- Match history
- Position rankings

---

# Position Evaluation

Every player is evaluated against every playable position.

The Position Engine computes:

- Position score
- Best position
- Second-best position
- Ranking
- Score difference

Positions supported:

- Goalkeeper
- Central Defender
- Central Defender Towards Wing
- Offensive Central Defender
- Wing Back
- Wing Back Towards Midfield
- Offensive Wing Back
- Defensive Wing Back
- Inner Midfielder
- Inner Midfielder Towards Wing
- Offensive Inner Midfielder
- Defensive Inner Midfielder
- Winger
- Winger Towards Midfield
- Offensive Winger
- Defensive Winger
- Forward
- Defensive Forward
- Forward Towards Wing
- Captain
- Set Piece Taker

Position weights are defined in the Position Engine configuration.

---

# TSI History

Historical evolution of Team Spirit Index.

For each synchronization:

- Date
- Previous TSI
- Current TSI
- Difference
- Trend

Charts available:

- Line chart
- Weekly change
- Seasonal evolution

---

# Purchases & Sales

Historical player transactions.

Fields:

- Purchase Date
- Sale Date
- Purchase Price
- Sale Price
- Profit/Loss
- Age
- TSI
- Best Position

---

# Next Match

Displays projected lineup information.

Future versions:

- Suggested lineup
- Expected ratings
- Tactical recommendations

---

# Training Integration

The Team module consumes information from the Training Engine.

For each player:

- Current training
- Estimated progress
- Expected pop date
- Minutes trained
- Effective training percentage

---

# Experience Integration

Displays:

- Experience level
- Experience points
- Progress to next level
- Matches since last increase

---

# Business Rules

- Historical player records are never deleted.
- Every synchronization recalculates position scores.
- Every synchronization recalculates training forecasts.
- Every synchronization recalculates experience progression.
- Position formulas are configuration-driven.
- UI never performs business calculations.

---

# Future Enhancements

- Automatic lineup builder
- AI position recommendations
- Player comparison
- Potential estimation
- Squad value analysis
- Fatigue monitoring
- Injury risk estimation
- Contract management

---

# Success Criteria

A manager should be able to understand the complete status of every player in under one minute, identify the best position, estimate future development, and make informed tactical and transfer decisions without leaving the Team module.
