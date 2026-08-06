# DATABASE

# Database Specification

## Purpose

Define the logical database model for HT Lens.

PostgreSQL is the primary datastore.

## Design Principles

- Third Normal Form where appropriate.
- Historical data preserved.
- Immutable event records.
- Indexed analytical queries.

## Core Entities

### users

Stores authenticated users.

Fields:

- id
- hattrick_user_id
- username
- language
- created_at

### clubs

- id
- club_id
- name
- country
- league_id
- stadium_id

### players

- id
- player_id
- club_id
- name
- nationality
- age
- tsi
- salary
- form
- stamina
- experience
- leadership
- loyalty
- mother_club
- specialty
- honesty
- aggression
- character

### player_skill_history

Stores historical skills by synchronization date.

### player_tsi_history

Stores TSI evolution.

### player_training_progress

Stores estimated training progress.

### player_experience_progress

Stores experience points.

### matches

- id
- match_id
- date
- competition
- home_club
- away_club
- score
- tactic
- ratings

### match_events

Every event from a match.

### lineups

Player positions by minute.

### economy_transactions

Weekly financial movements.

### stadium_history

Attendance and income history.

### transfers

Historical transfers.

### youth_players

Current youth academy players.

### former_youth_players

Graduated and sold academy players.

### leagues

League metadata.

### standings

Historical league tables.

### staff

Coach and assistants.

## Relationships

User
└── Club
    ├── Players
    ├── Matches
    ├── Economy
    ├── Stadium
    ├── Staff
    ├── Youth
    └── Transfers

## Indexes

Recommended:

- player_id
- match_id
- club_id
- sync_date
- week
- season

## Historical Strategy

Never overwrite:

- Skills
- TSI
- Economy
- Attendance
- Match ratings

Always append historical records.

## Future Tables

- simulations
- predictions
- ai_recommendations
- scouting
- market_statistics
- tactical_reports

## Migration Strategy

Alembic for schema migrations.

All migrations version-controlled.

No manual schema changes in production.
