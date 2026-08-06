# API

# HT Lens REST API Specification

## Purpose

The HT Lens API exposes all platform functionality through a versioned REST interface. It serves as the communication layer between the frontend, external clients, and the business engines.

---

# Design Principles

- RESTful architecture
- JSON request/response format
- Versioned endpoints
- Stateless communication
- OAuth2/JWT authentication
- Consistent error handling
- Pagination by default
- OpenAPI documentation generated automatically

Base URL:

```
/api/v1
```

---

# Authentication

## Login

```
GET /auth/login
```

Redirects the user to the official CHPP OAuth authorization flow.

---

## Callback

```
GET /auth/callback
```

Receives authorization code.

Creates user session.

Returns JWT.

---

## Current User

```
GET /users/me
```

Returns:

```json
{
  "id":1,
  "username":"manager",
  "clubId":12345
}
```

---

# Synchronization

## Full Synchronization

```
POST /sync/full
```

Starts complete synchronization.

Returns Job ID.

---

## Incremental Synchronization

```
POST /sync/incremental
```

Synchronizes only modified resources.

---

## Synchronization Status

```
GET /sync/{jobId}
```

Returns:

- Status
- Progress
- Started At
- Finished At
- Errors

---

# Players

## List Players

```
GET /players
```

Supports:

- pagination
- sorting
- filtering

Query parameters:

- age
- nationality
- specialty
- position
- transferListed

---

## Player Details

```
GET /players/{playerId}
```

Returns complete player profile.

---

## Player Position Rankings

```
GET /players/{playerId}/positions
```

Returns every calculated position.

---

## Player Training

```
GET /players/{playerId}/training
```

Returns:

- progress
- forecast
- history

---

## Player Experience

```
GET /players/{playerId}/experience
```

Returns experience progression.

---

# Matches

## Match List

```
GET /matches
```

Filters:

- competition
- season
- date

---

## Match Details

```
GET /matches/{matchId}
```

---

## Match Lineup

```
GET /matches/{matchId}/lineup
```

---

## Match Ratings

```
GET /matches/{matchId}/ratings
```

---

## Match Events

```
GET /matches/{matchId}/events
```

---

## Match Statistics

```
GET /matches/statistics
```

---

# League

```
GET /league
```

Returns standings.

---

```
GET /league/opponents
```

Returns opponent summaries.

---

```
GET /league/statistics
```

Returns league metrics.

---

# Training

```
GET /training
```

Current overview.

---

```
GET /training/history
```

Historical records.

---

```
GET /training/forecast
```

Future predictions.

---

# Economy

```
GET /economy
```

General financial information.

---

```
GET /economy/history
```

Historical weekly finances.

---

# Stadium

```
GET /stadium
```

Current stadium.

---

```
GET /stadium/history
```

Attendance history.

---

# Youth Academy

```
GET /youth
```

Current youth players.

---

```
GET /former-youth
```

Former academy players.

---

# Transfers

```
GET /transfers
```

Historical transfers.

---

# Comparison

```
POST /compare/matches
```

Compares two historical matches.

Body:

```json
{
  "matchA":123,
  "matchB":456
}
```

---

# Common Response

```json
{
  "success":true,
  "data":{},
  "errors":[],
  "meta":{}
}
```

---

# Error Response

```json
{
  "success":false,
  "message":"Validation error",
  "errors":[]
}
```

HTTP codes:

- 200 OK
- 201 Created
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 409 Conflict
- 422 Validation Error
- 500 Internal Server Error

---

# Pagination

Standard query parameters:

```
?page=1
&pageSize=50
```

Response:

```json
{
 "page":1,
 "pageSize":50,
 "total":527
}
```

---

# Versioning

Current version:

```
v1
```

Future versions:

- v2
- v3

Older versions remain supported according to the deprecation policy.

---

# Future Endpoints

- /simulation
- /ai
- /recommendations
- /forecast
- /scouting
- /market
- /reports
- /dashboard

---

# Success Criteria

The API must expose every business capability of HT Lens in a predictable, secure and well-documented manner, enabling web, mobile and third-party clients to consume the platform consistently.
