# TRAINING_ENGINE

# Training Engine Specification

## Purpose

The Training Engine is responsible for estimating, tracking and forecasting player development. It converts CHPP data into precise training progress, expected skill increases ("pops"), historical evolution and financial impact.

---

# Responsibilities

- Detect current training type automatically from CHPP.
- Calculate effective training for every player.
- Estimate progress toward the next skill level.
- Predict future skill pops.
- Maintain historical training records.
- Measure ROI of training and transfers.

---

# Inputs

- Training type
- Training intensity
- Stamina share
- Coach level
- Coach leadership
- Assistant coach levels (0–2 assistants)
- Player age
- Current skill level
- Minutes played
- Position played
- Training percentage by position
- Season / Week

---

# Functional Views

1. Training Overview
2. Training Settings
3. Player Progress
4. Pop History
5. Forecast
6. Purchases
7. Sales
8. Weekly History

---

# Player Table

Columns:

- Player
- Nationality
- Age
- Effective Training %
- Weeks Trained
- Current Skill
- Estimated Progress
- Expected Pop Week
- Player ID

---

# Training Settings

Display current configuration:

- Training Type
- Training Intensity
- Stamina Share
- Coach Level
- Coach Leadership
- Assistant Coaches
- Effective Training Speed

---

# Historical Progress

Store every week's snapshot.

Fields:

- Season
- Week
- Player
- Skill
- Estimated Progress
- Minutes
- Training %

Historical data is immutable.

---

# Pop History

For every completed pop:

- Player
- Skill
- Previous Level
- New Level
- Date
- Weeks Required
- Age

---

# Forecast

Predict:

- Next Skill Pop
- Estimated Week
- Remaining Weeks
- Confidence

---

# Minutes Calculation

90 minutes = 100% training.

Effective Training % = Minutes Played / 90

Examples:

- 90 min = 100%
- 45 min = 50%
- 30 min = 33.3%

If position receives partial training, multiply by positional percentage.

Examples:

- Wing Back under Winger training = 50%
- Winger under Playmaking training = 50%

Final Effective Training:

Minutes Factor × Position Factor

---

# Base Training Times

Reference player:

- 17 years old
- Solid coach
- Assistant level 5
- 100% intensity

| Skill | Base Weeks |
|--------|-----------:|
| Stamina | 1 |
| Goalkeeping | 4 |
| Defending | 8 |
| Playmaking | 7 |
| Passing | 5 |
| Winger | 5 |
| Scoring | 6 |
| Set Pieces | 2 |

---

# Modifiers

## Age

Each year above 17:

+6% training time

---

## Coach

Each level below Solid:

+10% training time

Excellent coach:

5% faster than Solid.

---

## Assistant Coaches

Each assistant contributes:

| Level | Bonus |
|------:|------:|
|1|3.5%|
|2|7.0%|
|3|10.5%|
|4|14.0%|
|5|17.5%|

Maximum two assistants.

Total Bonus = Assistant1 + Assistant2

Adjusted Weeks = Base Weeks / (1 + Total Bonus)

---

## Training Intensity

Each percentage below 100% increases required weeks proportionally.

---

# Progress Estimation

Estimated Progress = Weeks Completed / Adjusted Weeks

Expressed as percentage.

---

# Business Rules

- Training never exceeds 100%.
- Historical weeks are immutable.
- Predictions refresh after every synchronization.
- Position training percentages are configurable.
- All constants live in configuration.

---

# Outputs

- Progress %
- Expected Pop Date
- Remaining Weeks
- Historical Timeline
- Training ROI

---

# Future Enhancements

- Confidence intervals
- Bayesian estimation
- Multi-skill forecasting
- Transfer timing optimizer
- AI training planner
- Financial optimization

---

# Success Criteria

Managers should know who is training efficiently, how much progress each player has made, exactly when the next skill increase is expected, and how training decisions affect both sporting performance and long-term financial returns.
