"""Database (SQLAlchemy): kerk-accounts, tokens en inschrijvers.

Lokaal draait dit op SQLite (bestand in DATA_DIR); op Railway op Postgres via
de DATABASE_URL die Railway aanlevert. Dezelfde modellen werken op allebei.
"""

import os

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, func, inspect as sa_inspect, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)

import store


def _database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        # Railway levert 'postgres://...'; SQLAlchemy wil 'postgresql+psycopg2://'.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url
    # Lokale terugval: SQLite-bestand in de data-map.
    os.makedirs(store.DATA_DIR, exist_ok=True)
    pad = os.path.join(store.DATA_DIR, "app.db").replace("\\", "/")
    return f"sqlite:///{pad}"


DATABASE_URL = _database_url()
_is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Church(Base):
    __tablename__ = "churches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    naam: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    wachtwoord_hash: Mapped[str] = mapped_column(String(200))
    email_geverifieerd: Mapped[bool] = mapped_column(Boolean, default=False)

    # Instellingen
    kanaal_url: Mapped[str] = mapped_column(String(500), default="")
    auto_versturen: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_scan: Mapped[bool] = mapped_column(Boolean, default=True)  # automatisch nieuwe diensten oppikken
    tijdzone: Mapped[str] = mapped_column(String(50), default="Europe/Amsterdam")
    admin_taal: Mapped[str] = mapped_column(String(5), default="auto")
    inschrijf_taal: Mapped[str] = mapped_column(String(5), default="auto")
    communicatie_taal: Mapped[str] = mapped_column(String(5), default="nl")
    # De kerk bepaalt het verzendmoment (in de kerk-tijdzone). Wekelijks: de hele
    # bundel op verzend_dag; dagelijks: dag 1 op verzend_dag, dan elke dag verder.
    verzend_dag: Mapped[int] = mapped_column(Integer, default=0)  # 0=ma .. 6=zo
    verzend_tijd: Mapped[str] = mapped_column(String(5), default="07:00")  # "HH:MM"
    # Bij "kerk moet goedkeuren": toch versturen als er op het verzendmoment nog
    # geen goedkeuring is?
    versturen_zonder_goedkeuring: Mapped[bool] = mapped_column(Boolean, default=False)

    aangemaakt: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    tokens: Mapped[list["EmailToken"]] = relationship(
        back_populates="kerk", cascade="all, delete-orphan"
    )
    inschrijvers: Mapped[list["Subscriber"]] = relationship(
        back_populates="kerk", cascade="all, delete-orphan"
    )


class Medebeheerder(Base):
    """Extra login-account dat dezelfde kerk beheert (zonder aparte rollen)."""

    __tablename__ = "medebeheerders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kerk_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"))
    naam: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    wachtwoord_hash: Mapped[str] = mapped_column(String(200), default="")
    email_geverifieerd: Mapped[bool] = mapped_column(Boolean, default=False)
    token: Mapped[str] = mapped_column(String(64), default="", index=True)  # uitnodiging/reset
    aangemaakt: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class EmailToken(Base):
    """Eenmalige token voor e-mailverificatie en wachtwoord-reset."""

    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kerk_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    soort: Mapped[str] = mapped_column(String(20))  # "verify" of "reset"
    verloopt: Mapped[DateTime] = mapped_column(DateTime)
    gebruikt: Mapped[bool] = mapped_column(Boolean, default=False)

    kerk: Mapped["Church"] = relationship(back_populates="tokens")


class Subscriber(Base):
    """Gemeentelid dat de overdenkingen ontvangt (gebruikt vanaf het volgende blok)."""

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kerk_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"))
    naam: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), index=True)
    telefoon: Mapped[str] = mapped_column(String(40), default="")

    kanaal: Mapped[str] = mapped_column(String(20), default="email")  # email/whatsapp/app
    frequentie: Mapped[str] = mapped_column(String(20), default="wekelijks")  # of "dagelijks"
    ontvang_dag: Mapped[int] = mapped_column(Integer, default=0)  # wekelijks: 0=ma..6=zo
    ontvang_tijd: Mapped[str] = mapped_column(String(5), default="07:00")  # "HH:MM" (kerktijdzone)

    bevestigd: Mapped[bool] = mapped_column(Boolean, default=False)  # double opt-in
    bevestig_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    voorkeur_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    aangemaakt: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    kerk: Mapped["Church"] = relationship(back_populates="inschrijvers")


class Uitzending(Base):
    """Een door de kerk uitgezonden (en verwerkte) dienst; stuurt de bezorging aan."""

    __tablename__ = "uitzendingen"
    __table_args__ = (UniqueConstraint("kerk_id", "video_id", name="uq_kerk_video"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kerk_id: Mapped[int] = mapped_column(ForeignKey("churches.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[str] = mapped_column(String(200), index=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    titel: Mapped[str] = mapped_column(String(300), default="")
    datum: Mapped[Date] = mapped_column(Date)          # datum van de dienst
    week_start: Mapped[Date] = mapped_column(Date)     # maandag van de overdenkingsweek
    verwerkt_op: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    goedgekeurd: Mapped[bool] = mapped_column(Boolean, default=False)
    goedgekeurd_op: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    goedgekeurd_door: Mapped[str] = mapped_column(String(320), default="")
    goedkeur_token: Mapped[str] = mapped_column(String(64), default="", index=True)


class Verzending(Base):
    """Logregel: welk dagdeel van welke uitzending naar welke inschrijver is gestuurd.

    Voorkomt dubbele verzending (idempotentie). dag: 0 = wekelijks (heel boekje),
    1..7 = dagelijkse dagdelen.
    """

    __tablename__ = "verzendingen"
    __table_args__ = (
        UniqueConstraint("uitzending_id", "subscriber_id", "dag", name="uq_verzending"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uitzending_id: Mapped[int] = mapped_column(ForeignKey("uitzendingen.id", ondelete="CASCADE"), index=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id", ondelete="CASCADE"), index=True)
    dag: Mapped[int] = mapped_column(Integer, default=0)
    verzonden_op: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


def _voeg_ontbrekende_kolommen_toe():
    """Lichte auto-migratie: voeg nieuwe modelkolommen toe aan bestaande tabellen.

    create_all() maakt alleen ontbrekende tabellen, geen ontbrekende kolommen.
    Tijdens deze snelle ontwikkelfase voorkomt dit dat een schema-uitbreiding de
    bestaande (Railway-)database breekt. Voor complexere migraties later: Alembic.
    """
    insp = sa_inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        bestaand = {c["name"] for c in insp.get_columns(table.name)}
        for kol in table.columns:
            if kol.name in bestaand:
                continue
            coltype = kol.type.compile(dialect=engine.dialect)
            standaard = ""
            arg = getattr(kol.default, "arg", None)
            if arg is not None and not callable(arg):
                if isinstance(arg, bool):
                    waarde = ("1" if arg else "0") if _is_sqlite else ("true" if arg else "false")
                elif isinstance(arg, (int, float)):
                    waarde = str(arg)
                else:
                    waarde = "'" + str(arg).replace("'", "''") + "'"
                standaard = f" DEFAULT {waarde}"
            with engine.begin() as conn:
                conn.execute(text(
                    f'ALTER TABLE {table.name} ADD COLUMN {kol.name} {coltype}{standaard}'
                ))


def init_db():
    Base.metadata.create_all(engine)
    _voeg_ontbrekende_kolommen_toe()
