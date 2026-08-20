"""Initial schema: núcleo del sync con player_snapshots particionada.

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "chpp_tokens",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("oauth_token_enc", sa.LargeBinary, nullable=False),
        sa.Column("oauth_secret_enc", sa.LargeBinary, nullable=False),
        sa.Column("key_version", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("ht_user_id", sa.BigInteger),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("ht_team_id", sa.BigInteger, nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("league_name", sa.String(128)),
        sa.Column("series_name", sa.String(128)),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("ht_player_id", sa.BigInteger, nullable=False, unique=True, index=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), index=True),
        sa.Column("first_name", sa.String(64), nullable=False),
        sa.Column("last_name", sa.String(64), nullable=False),
        sa.Column("left_team_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "syncs",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(2000)),
    )

    # Particionada: PK física debe incluir la clave de partición.
    #
    # Una sentencia por `execute`. El driver asíncrono (asyncpg) manda cada SQL
    # como sentencia preparada, y Postgres no acepta varias dentro de una:
    # "cannot insert multiple commands into a prepared statement". Con un
    # driver síncrono el mismo bloque pasaba, así que esto solo se ve al
    # migrar de verdad contra Postgres.
    op.execute("""
        CREATE TABLE player_snapshots (
            id              bigint GENERATED ALWAYS AS IDENTITY,
            sync_id         bigint NOT NULL REFERENCES syncs(id),
            player_id       bigint NOT NULL REFERENCES players(id),
            captured_at     timestamptz NOT NULL,
            age_years       smallint NOT NULL,
            age_days        smallint NOT NULL,
            tsi             integer NOT NULL,
            form            smallint NOT NULL,
            stamina         smallint NOT NULL,
            experience      smallint NOT NULL,
            salary          integer NOT NULL,
            keeper          smallint,
            defending       smallint,
            playmaking      smallint,
            winger          smallint,
            passing         smallint,
            scoring         smallint,
            set_pieces      smallint,
            injury_level    smallint NOT NULL DEFAULT -1,
            is_transfer_listed boolean NOT NULL DEFAULT false,
            content_hash    bytea NOT NULL,
            PRIMARY KEY (id, captured_at)
        ) PARTITION BY RANGE (captured_at)
    """)
    op.execute(
        "CREATE INDEX ix_ps_player_time "
        "ON player_snapshots (player_id, captured_at DESC)"
    )
    # Partición por defecto; el worker de mantenimiento crea las mensuales.
    op.execute(
        "CREATE TABLE player_snapshots_default "
        "PARTITION OF player_snapshots DEFAULT"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS player_snapshots CASCADE")
    for t in ("syncs", "players", "teams", "chpp_tokens", "users"):
        op.drop_table(t)
