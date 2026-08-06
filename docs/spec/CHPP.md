# CHPP

# CHPP Integration Specification

## Purpose

This document defines how HT Lens integrates with the official CHPP API.

## Objectives

- Authenticate users through OAuth.
- Synchronize club data automatically.
- Preserve historical snapshots.
- Minimize API calls.
- Support incremental synchronization.

## Synchronization Strategy

### Initial Sync

Import all available information:

- Club
- Players
- Matches
- Economy
- Stadium
- League
- Transfers
- Youth Academy
- Staff

### Incremental Sync

Triggered:

- Manual synchronization
- Scheduled jobs
- Login
- Weekly training update
- Match completion

## Data Categories

### Static

- Player ID
- Club ID
- Nationality
- Birth information

### Slowly Changing

- Skills
- Experience
- Leadership
- TSI
- Salary

### Time Series

- Match ratings
- Training progress
- Economy
- Stadium attendance
- Transfers

## Synchronization Pipeline

CHPP
↓
OAuth
↓
Fetch XML
↓
Validation
↓
Normalization
↓
Persistence
↓
Business Engines
↓
Dashboards

## Error Handling

- Retry transient failures.
- Respect CHPP rate limits.
- Log synchronization history.
- Detect partial imports.

## Historical Policy

HT Lens never deletes historical data.

Every synchronization creates or updates historical records suitable for trend analysis.

## Recommended Frequency

- Club information: daily
- Players: daily
- Economy: weekly
- Matches: after every match
- League: after every league round
- Training: after training update

## Future Extensions

- Background synchronization queue
- Differential imports
- Smart cache invalidation
- Multi-account support
