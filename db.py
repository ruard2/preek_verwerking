"""Database (SQLAlchemy): kerk-accounts, tokens en inschrijvers.

Lokaal draait dit op SQLite (bestand in DATA_DIR); op Railway op Postgres via
de DATABASE_URL die Railway aanlevert. Dezelfde modellen werken op allebei.
"""

import logging
import os

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, func, inspect as sa_inspect, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)

import store

_log = logging.getLogger("aftersermon.db")


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
    community_tools_organization_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    community_tools_user_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    naam: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    wachtwoord_hash: Mapped[str] = mapped_column(String(200))
    email_geverifieerd: Mapped[bool] = mapped_column(Boolean, default=False)

    # Instellingen
    kanaal_url: Mapped[str] = mapped_column(String(500), default="")
    auto_versturen: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_scan: Mapped[bool] = mapped_column(Boolean, default=True)  # automatisch nieuwe diensten oppikken
    # Preken van afgelopen zondag vooraf (achtergrond) transcriberen, zodat ze
    # klaarstaan als de beheerder inlogt.
    auto_verwerken: Mapped[bool] = mapped_column(Boolean, default=False)
    tijdzone: Mapped[str] = mapped_column(String(50), default="Europe/Amsterdam")
    admin_taal: Mapped[str] = mapped_column(String(5), default="auto")
    inschrijf_taal: Mapped[str] = mapped_column(String(5), default="auto")
    communicatie_taal: Mapped[str] = mapped_column(String(5), default="nl")
    # Bijbeltekst: volledig vers tonen of alleen de verwijzing; en welke vertaling
    # ("vrij" = publiek domein per taal, of een specifieke zoals nbv21/hsv/niv/esv).
    citaat_volledig: Mapped[bool] = mapped_column(Boolean, default=True)
    bijbelvertaling: Mapped[str] = mapped_column(String(20), default="vrij")
    # De kerk bepaalt het verzendmoment (in de kerk-tijdzone). Wekelijks: de hele
    # bundel op verzend_dag; dagelijks: dag 1 op verzend_dag, dan elke dag verder.
    verzend_dag: Mapped[int] = mapped_column(Integer, default=0)  # 0=ma .. 6=zo
    verzend_tijd: Mapped[str] = mapped_column(String(5), default="07:00")  # "HH:MM"
    # Bij "kerk moet goedkeuren": toch versturen als er op het verzendmoment nog
    # geen goedkeuring is?
    versturen_zonder_goedkeuring: Mapped[bool] = mapped_column(Boolean, default=False)
    # Toon onderaan elke mail dat de tekst met AI is gemaakt (aanrader).
    ai_disclaimer: Mapped[bool] = mapped_column(Boolean, default=True)
    # Eigen logo van de kerk (base64 van de afbeelding) + het content-type. Wordt
    # bovenaan de mail en op de inschrijfpagina getoond via /logo/{kerk_id}.
    logo: Mapped[str] = mapped_column(Text, default="")
    logo_type: Mapped[str] = mapped_column(String(80), default="")
    # Accentkleur (hex) voor de mails en publieke pagina's van deze kerk.
    accentkleur: Mapped[str] = mapped_column(String(7), default="#2c5f2d")
    # Kwaliteitsknoppen voor de overdenkingen: toon en lengte.
    toon: Mapped[str] = mapped_column(String(20), default="warm")
    lengte: Mapped[str] = mapped_column(String(20), default="middel")
    # Welke uitvoer(en) de kerk maakt, komma-gescheiden. Keuze uit:
    # dagstukjes, preeksamenvatting, preektranscript, nabespreking.
    uitvoer_typen: Mapped[str] = mapped_column(String(120), default="dagstukjes")

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
    community_tools_user_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
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
    # Welke dienst(en) wil de inschrijver: "beide" | "ochtend" | "avond".
    dienstvoorkeur: Mapped[str] = mapped_column(String(10), default="beide")
    # Push-abonnement (browser) als JSON-tekst; leeg = geen push. Het gekozen
    # kanaal ("email" | "push" | "beide") staat in het bestaande veld `kanaal`.
    push_abonnement: Mapped[str] = mapped_column(Text, default="")
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
    # Dagdeel van de dienst: "ochtend" | "avond" | "" (onbekend). Voor het
    # filteren op dienstvoorkeur van de inschrijver.
    dagdeel: Mapped[str] = mapped_column(String(10), default="")


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
    Deze stap voegt nieuwe ADD-COLUMN-uitbreidingen veilig toe. Kan alléén
    kolommen TOEVOEGEN — voor renames, type-wijzigingen of datamigraties is
    Alembic nodig (zie ALEMBIC.md). Elke kolom staat in een eigen transactie én
    try/except, zodat één mislukte kolom nooit de app-start op Railway breekt.
    """
    try:
        insp = sa_inspect(engine)
    except Exception:  # noqa: BLE001
        _log.exception("Auto-migratie: kon de database niet inspecteren; overslaan")
        return
    for table in Base.metadata.sorted_tables:
        try:
            if not insp.has_table(table.name):
                continue
            bestaand = {c["name"] for c in insp.get_columns(table.name)}
        except Exception:  # noqa: BLE001
            _log.exception("Auto-migratie: tabel %s niet leesbaar; overslaan", table.name)
            continue
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
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        f'ALTER TABLE {table.name} ADD COLUMN {kol.name} {coltype}{standaard}'
                    ))
                _log.info("Auto-migratie: kolom %s.%s toegevoegd", table.name, kol.name)
            except Exception:  # noqa: BLE001 — nooit de opstart blokkeren
                _log.exception(
                    "Auto-migratie: kolom %s.%s toevoegen mislukt", table.name, kol.name
                )


def _maak_index(sql):
    """Idempotente index-aanmaak die de opstart nooit mag breken."""
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:  # noqa: BLE001
        _log.exception("Index aanmaken mislukt (overgeslagen): %s", sql[:60])


def init_db():
    Base.metadata.create_all(engine)
    _voeg_ontbrekende_kolommen_toe()
    # create_all voegt geen indexes toe aan bestaande tabellen. Deze unieke
    # centrale koppelingen moeten ook bij upgrades afgedwongen blijven.
    _maak_index(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_churches_community_tools_organization "
        "ON churches (community_tools_organization_id)"
    )
    _maak_index(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_churches_community_tools_user "
        "ON churches (community_tools_user_id)"
    )
    _maak_index(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_medebeheerders_community_tools_user "
        "ON medebeheerders (community_tools_user_id)"
    )
