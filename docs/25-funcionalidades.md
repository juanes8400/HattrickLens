# HT Lens — Features

Texto de referencia para presentar la aplicación fuera de ella: la ficha de
Hattrick, el foro, el repositorio. Escrito en inglés a propósito, que es la
lengua en la que se presentan las aplicaciones de Hattrick.

**Este fichero describe lo CONSTRUIDO, no lo planeado.** Para el plan está
`68-catalogo-vistas.md`, que enumera vistas que en su mayoría no existen
todavía; confundirlos sería prometer lo que no hay.

Las mismas descripciones, traducidas, se enseñan dentro de la aplicación en
Transparencia → «Qué hace cada módulo». Si cambias una, cambia la otra:
[`backend/app/application/queries/transparencia.py`](../backend/app/application/queries/transparencia.py).

---

## Management dashboard

Provides a decision-oriented overview of the club, including current cash,
recent financial balance, wage pressure, squad strength, training efficiency,
active alerts, league-relative strength and a recommended starting eleven.

## Club and staff monitoring

Displays the current team spirit, confidence, supporters, youth investment,
coach and specialist staff. It also keeps weekly historical series for club
mood, supporters and staff levels, and explains the contribution of each staff
member.

## Squad and player analysis

Provides a complete sortable and exportable squad table and detailed player
profiles. It includes skills, form, stamina, experience, loyalty, TSI, salary,
HTMS, HTMS28, nationality, specialty, personality, injuries, purchase
information, transfer status, position ratings and weekly development history.
Former players receive a separate financial profile with their time at the
club, accumulated wages, listing costs, sale proceeds and ROI.

## Position ratings and line-up optimizer

Evaluates every player in 19 positional and individual-order variants, plus
captain, set-piece taker and penalty-taker roles. It recommends the best
starting eleven for any legal formation, supports central/flank distributions
and individual orders, calculates sector contributions and compares the
recommendation with the line-up already submitted to Hattrick.

## Training planner and player development

Displays the current training type, intensity, stamina share, coach, assistants
and effective training speed. It estimates progress toward the next skill level
using player age, staff, intensity and actual minutes played in trainable
positions. It tracks confirmed skill increases, experience, loyalty and stamina
development, forecasts future skill levels and can retrospectively compare all
training types after the week's matches to show which option would have used
the played minutes most efficiently.

## Youth academy management

Manages the youth squad using revealed current skills, revealed potential
skills, age, promotion eligibility and HTMS28 ranges. It classifies youth
players, identifies urgent promotion deadlines, recommends primary and
secondary training, proposes the next youth line-up and tracks scouts, scouting
regions, academy costs, youth sales and former academy players.

## Transfer history, costs and ROI

Builds a historical transfer ledger for bought players, academy graduates, sold
players and dismissed players. It calculates purchase costs, accumulated wages,
transfer-listing costs, agent commissions, net sale proceeds, resale
commissions, profit and ROI. The module includes analysis by season, purchase
week, sale week, age, training type, highest skill and auction closing time. It
also tracks individual transfer-listing attempts, asking prices, bids, outcomes
and manually recorded listing views.

For players who left before HT Lens was tracking them, Hattrick publishes no
historical salary. Those wages are estimated from TSI and age against the
club's own readings, and every estimated figure is labelled as such: each row
is marked as measured, estimated or unknown, and the totals can be shown with
all rows, without the unknown ones, or with measured data only.

## Match history and performance analysis

Provides match history by season and competition, home/away records, goals,
Hatstats, chance creation, best sector ratings and conversion rates. Each match
can be opened for a sector-by-sector comparison, rating radar, chance analysis
and explanation of the result.

## League analysis and season projection

Displays the official league table with total, home and away views, the full
fixture calendar and the real historical development of positions and points.
It provides a clearly labelled season projection with expected points, final
position probabilities, title and top-4 probabilities, mathematical best/worst
limits and a forecast for every team. It also compares squad TSI, form and
stamina across the series and creates a best real-rated league line-up for a
selected round or full season.

## Cup decision center

Tracks the team's current Cup, official round, next opponent, number of wins
required for the title and the prize milestones that can still be reached. It
explains the consequence of winning or losing, including movement between Cup
levels where available. It also provides opponent analysis, a clearly labelled
probability estimate, observed Cup income, a separate future gate-income
scenario, a 120-minute stamina preparation and an indicative penalty-taking
order.

## Opponent scouting

Analyses league and Cup opponents using the public information Hattrick
publishes about their recent matches. It estimates the opponent's probable
eleven, compares TSI, form, stamina and experience, identifies recent
transfers, manager activity, habitual formations and tactics, attacking-side
rotation and visible players. It provides man-marking suggestions and a
seven-zone pitch comparison. For the manager's own side, it can use the
official predicted ratings of match orders already submitted to Hattrick; for
the opponent, it uses completed-match information only.

## Economy tracking and cash scenarios

Tracks the official Hattrick income and expense categories without renaming or
merging them. It displays current-week finances, historical income, expenses,
profit and cash, accumulated balances and a Sankey flow for several time
windows. Future cash values are presented separately and explicitly as
scenarios rather than actual results. The module supports structural forecasts,
uncertainty ranges and, after enough history is available, time-series model
comparison. It also reports how many weeks the current cash lasts, both
including and excluding transfer activity.

## Stadium attendance and demand analysis

Analyses real stadium capacity, attendance, occupancy, revenue and demand by
sector. It distinguishes measurable demand from censored demand when a sector
sells out and identifies matches where capacity may have limited attendance.
