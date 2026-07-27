"""Database (SQLAlchemy): kerk-accounts, tokens en inschrijvers.

Lokaal draait dit op SQLite (bestand in DATA_DIR); op Railway op Postgres via
de DATABASE_URL die Railway aanlevert. Dezelfde modellen werken op allebei.
"""

import os

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func,
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
    frequentie: Mapped[str] = mapped_column(String(20), default="wekelijks")  # of "dagelijks"

    aangemaakt: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    tokens: Mapped[list["EmailToken"]] = relationship(
        back_populates="kerk", cascade="all, delete-orphan"
    )
    inschrijvers: Mapped[list["Subscriber"]] = relationship(
        back_populates="kerk", cascade="all, delete-orphan"
    )


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
    frequentie: Mapped[str] = mapped_column(String(20), default="wekelijks")
    per_dag: Mapped[int] = mapped_column(Integer, default=1)  # 1 of 2 diensten
    taal: Mapped[str] = mapped_column(String(10), default="")

    bevestigd: Mapped[bool] = mapped_column(Boolean, default=False)  # double opt-in
    voorkeur_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    aangemaakt: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    kerk: Mapped["Church"] = relationship(back_populates="inschrijvers")


def init_db():
    Base.metadata.create_all(engine)
