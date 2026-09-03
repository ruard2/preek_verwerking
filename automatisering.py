"""Automatisering: nieuwe diensten scannen, verwerken, laten goedkeuren en
op het juiste moment naar inschrijvers versturen.

Draait als achtergrond-lus in dezelfde container (start()). Alle tijdsbeslissingen
gebeuren in de tijdzone van de kerk. De verzendlog (Verzending) maakt het
idempotent: niets wordt dubbel verstuurd, ook niet als de lus vaker draait.
"""

import logging
import secrets
import threading
import time as _time
import traceback

_log = logging.getLogger("aftersermon.auto")
from datetime import datetime, time as dtime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from sqlalchemy import select

import brevo
import kerkdienstgemist
import levering
import store
import transcript as ts
import ui_i18n
from db import Church, SessionLocal, Subscriber, Uitzending, Verzending

# Alleen diensten van de afgelopen zoveel dagen automatisch oppikken (voorkomt
# dat bij de eerste scan de hele back-catalogus verwerkt wordt).
SCAN_TERUG_DAGEN = 28
# Hoeveel nieuwe diensten per tick maximaal verwerken (kosten/tijd spreiden).
MAX_PER_TICK = 12
# Niet eindeloos catch-uppen: alleen momenten van de afgelopen zoveel dagen.
GRACE_DAGEN = 8
INTERVAL_SECONDEN = 300


# ---------- Pure planningslogica (goed te testen) ----------
def komende_maandag(d):
    """De eerstvolgende maandag ná datum d (of een week later als d maandag is)."""
    dagen = (7 - d.weekday()) % 7 or 7
    return d + timedelta(days=dagen)


def parse_tijd(s):
    try:
        u, m = (s or "07:00").split(":")[:2]
        return dtime(int(u) % 24, int(m) % 60)
    except Exception:  # noqa: BLE001
        return dtime(7, 0)


def geplande_momenten(week_start, kerk, sub):
    """(dag, lokaal-naïef datetime) waarop deze inschrijver iets moet ontvangen.

    De KERK bepaalt het verzendmoment (verzend_dag + verzend_tijd, kerk-tijdzone);
    de inschrijver kiest alleen de frequentie. dag 0 = het hele weekboekje
    (wekelijks); 1..7 = losse dagdelen (dagelijks, vanaf verzend_dag).
    """
    t = parse_tijd(getattr(kerk, "verzend_tijd", None) or "07:00")
    basis = week_start + timedelta(days=(getattr(kerk, "verzend_dag", 0) or 0) % 7)
    if sub.frequentie == "dagelijks":
        return [(k, datetime.combine(basis + timedelta(days=k - 1), t)) for k in range(1, 8)]
    return [(0, datetime.combine(basis, t))]


def due_momenten(week_start, kerk, sub, nu_lokaal, grace_dagen=GRACE_DAGEN):
    """Welke (dag, moment) zijn nu verschuldigd: gepland <= nu en niet te oud."""
    due = []
    for dag, moment in geplande_momenten(week_start, kerk, sub):
        if moment <= nu_lokaal and (nu_lokaal - moment) <= timedelta(days=grace_dagen):
            due.append((dag, moment))
    return due


# ---------- Kanaal / tijdzone ----------
def _tz(kerk):
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(kerk.tijdzone or "Europe/Amsterdam")
    except Exception:  # noqa: BLE001
        return ZoneInfo("Europe/Amsterdam")


def _nu_lokaal(kerk):
    tz = _tz(kerk)
    return datetime.now(tz).replace(tzinfo=None) if tz else datetime.now()


def _kanaal_diensten(kerk, vernieuw=False):
    url = kerk.kanaal_url or ""
    import main  # laat-import om circulaire import te vermijden

    typ, soort = main._classificeer(url)
    if not typ or soort != "kanaal":
        return []
    # Gebruik exact dezelfde gecachete kanaallijst als de demo. Een handmatige
    # scan (vernieuw=True) haalt een verse lijst op i.p.v. de cache.
    return main._laad_diensten(typ, url, vernieuw=vernieuw)


# ---------- Scannen + verwerken ----------
def dagdeel(dienst):
    """Bepaal of een dienst 'ochtend' of 'avond' is (of '' bij twijfel).

    Eerst op titel/label (ochtend/avond, ook Engels/Afrikaans), anders op tijd
    (vóór 13:00 = ochtend).
    """
    tekst = ((dienst.get("titel") or "") + " " + (dienst.get("label") or "")).lower()
    if any(w in tekst for w in ("ochtend", "morgen", "morning", "oggend")):
        return "ochtend"
    if any(w in tekst for w in ("avond", "middag", "evening", "afternoon", "aand")):
        return "avond"
    tijd = dienst.get("tijd") or ""
    if len(tijd) >= 2 and tijd[:2].isdigit():
        return "ochtend" if int(tijd[:2]) < 13 else "avond"
    return ""


def _wil_ontvangen(sub, uit):
    """Wil deze inschrijver deze dienst? Bij onbekend dagdeel: altijd ja."""
    voorkeur = getattr(sub, "dienstvoorkeur", "beide") or "beide"
    dd = getattr(uit, "dagdeel", "") or ""
    if voorkeur == "beide" or not dd:
        return True
    return voorkeur == dd


def scan_kerk(db, kerk, base_url, nu_lokaal=None, vernieuw=False):
    """Zoek nieuwe recente diensten, verwerk ze en maak een Uitzending aan."""
    if not (kerk.kanaal_url or "").strip():
        return 0
    nu_lokaal = nu_lokaal or _nu_lokaal(kerk)
    grens = nu_lokaal.date() - timedelta(days=SCAN_TERUG_DAGEN)

    diensten = _kanaal_diensten(kerk, vernieuw=vernieuw)
    verwerkt = 0
    for d in diensten:
        if verwerkt >= MAX_PER_TICK:
            break
        if d.get("gepland"):
            continue
        datum = _naar_datum(d.get("datum"))
        if not datum or datum < grens or datum > nu_lokaal.date():
            continue
        video_id = d.get("id")
        bestaat = db.scalar(
            select(Uitzending).where(
                Uitzending.kerk_id == kerk.id, Uitzending.video_id == video_id
            )
        )
        if bestaat:
            continue
        # Alleen vastleggen en aanklikbaar maken — NIET automatisch verwerken.
        # De (dure) transcript/AI-verwerking gebeurt pas op verzoek: als de
        # beheerder de dienst opent, of lui op het moment van bezorging.
        uit = Uitzending(
            kerk_id=kerk.id, video_id=video_id, url=d["url"],
            titel=d.get("titel") or d.get("label") or "Dienst",
            datum=datum, week_start=komende_maandag(datum),
            dagdeel=dagdeel(d),
            goedgekeurd=bool(kerk.auto_versturen),
            goedkeur_token=secrets.token_urlsafe(24),
        )
        db.add(uit)
        db.commit()
        verwerkt += 1
        if not kerk.auto_versturen:
            _stuur_goedkeur_mail(kerk, uit, base_url)
    return verwerkt


def preverwerk_kerk(db, kerk, base_url, nu_lokaal=None):
    """Transcribeer (achtergrond) de dienst(en) van afgelopen zondag vast, zodat ze
    klaarstaan als de beheerder inlogt. Alleen transcript + opschonen; het genereren
    van dagstukjes/samenvatting/vragen gebeurt pas op aanvraag. Idempotent: al
    verwerkte diensten worden overgeslagen (hun transcript zit al in de opslag)."""
    if not kerk.auto_verwerken:
        return 0
    import main
    nu_lokaal = nu_lokaal or _nu_lokaal(kerk)
    vandaag = nu_lokaal.date()
    zondag = vandaag - timedelta(days=(vandaag.weekday() + 1) % 7)  # meest recente zondag
    uitzendingen = db.scalars(
        select(Uitzending).where(
            Uitzending.kerk_id == kerk.id, Uitzending.datum == zondag
        )
    ).all()
    gedaan = 0
    for uit in uitzendingen:
        bewaard = store.resultaat_ophalen(uit.video_id)
        if bewaard and (bewaard.get("transcript_ruw") or "").strip():
            continue  # al (voor)verwerkt
        try:
            main.verwerk_en_bewaar(
                uit.url, alleen_transcript=True,
                bijbel=main.bijbel_van_kerk(kerk),
                uitvoer_typen=main.uitvoer_van_kerk(kerk),
            )
            gedaan += 1
        except Exception:  # noqa: BLE001 — één dienst mag de rest niet blokkeren
            _log.exception("Vooraf transcriberen mislukt voor uitzending %s", uit.id)
    return gedaan


def _stuur_goedkeur_mail(kerk, uit, base_url):
    goedkeur = f"{base_url}/api/uitzending/goedkeuren?token={uit.goedkeur_token}"
    bewerk = f"{base_url}/uitzending?token={uit.goedkeur_token}"
    t = ui_i18n.messages(kerk.communicatie_taal)
    html = (
        f"<p>{t['approval_ready'].format(date=uit.datum.isoformat(), title=uit.titel)}</p>"
        f'<p><a href="{bewerk}">{t["review"]}</a></p>'
        f'<p><a href="{goedkeur}" style="background:#2c5f2d;color:#fff;'
        f'padding:.6em 1.2em;border-radius:.4em;text-decoration:none">'
        f'{t["approve"]}</a></p>'
    )
    brevo.verzend(
        kerk.email, t["approval_subject"].format(title=uit.titel), html,
        tekst=f'{t["review"]}: {bewerk}\n{t["approve"]}: {goedkeur}',
    )


# ---------- Bezorgen ----------
def bezorg_kerk(db, kerk, base_url, nu_lokaal=None):
    """Verstuur alle nu-verschuldigde dagdelen naar de inschrijvers."""
    nu_lokaal = nu_lokaal or _nu_lokaal(kerk)
    verzonden = 0
    uitzendingen = list(db.scalars(
        select(Uitzending).where(Uitzending.kerk_id == kerk.id)
    ))
    inschrijvers = [
        s for s in db.scalars(select(Subscriber).where(Subscriber.kerk_id == kerk.id))
        if s.bevestigd
    ]
    if not inschrijvers:
        return 0

    for uit in uitzendingen:
        mag = uit.goedgekeurd or kerk.versturen_zonder_goedkeuring
        if not mag:
            continue
        # Is er nú iets verschuldigd voor iemand? Zo niet: niets doen en zeker
        # niet verwerken (bespaart kosten tot bezorging echt aan de orde is).
        iets_due = any(
            due_momenten(uit.week_start, kerk, s, nu_lokaal) for s in inschrijvers
        )
        if not iets_due:
            continue
        bewaard = store.resultaat_ophalen(uit.video_id)
        if not bewaard or not bewaard.get("data"):
            import main  # lui verwerken: nu pas transcript + AI

            try:
                main.verwerk_en_bewaar(
                    uit.url, bijbel=main.bijbel_van_kerk(kerk),
                    uitvoer_typen=main.uitvoer_van_kerk(kerk),
                )
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                continue
            bewaard = store.resultaat_ophalen(uit.video_id)
        if not bewaard or not bewaard.get("data"):
            continue
        data = bewaard["data"]
        for sub in inschrijvers:
            if not _wil_ontvangen(sub, uit):
                continue  # inschrijver wil dit dagdeel niet
            for dag, _moment in due_momenten(uit.week_start, kerk, sub, nu_lokaal):
                al = db.scalar(select(Verzending).where(
                    Verzending.uitzending_id == uit.id,
                    Verzending.subscriber_id == sub.id, Verzending.dag == dag,
                ))
                if al:
                    continue
                alleen_dag = None if dag == 0 else dag - 1
                try:
                    levering.verstuur_een(kerk, data, base_url, sub, alleen_dag)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                    continue
                db.add(Verzending(uitzending_id=uit.id, subscriber_id=sub.id, dag=dag))
                db.commit()
                verzonden += 1
    return verzonden


# ---------- Lus ----------
def tick(base_url):
    db = SessionLocal()
    try:
        for kerk in db.scalars(select(Church)):
            if not (kerk.kanaal_url or "").strip():
                continue
            try:
                nieuw = scan_kerk(db, kerk, base_url) if kerk.auto_scan else 0
                if kerk.auto_verwerken:
                    preverwerk_kerk(db, kerk, base_url)
                verzonden = bezorg_kerk(db, kerk, base_url)
                if nieuw or verzonden:
                    _log.info(
                        "kerk %s: %s nieuwe dienst(en), %s mail(s) verzonden",
                        kerk.id, nieuw, verzonden,
                    )
            except Exception:  # noqa: BLE001 — één kerk mag de rest niet blokkeren
                _log.exception("Fout bij verwerken/bezorgen voor kerk %s", kerk.id)
                db.rollback()
    finally:
        db.close()


def start(base_url, interval=INTERVAL_SECONDEN):
    def lus():
        while True:
            try:
                tick(base_url)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            _time.sleep(interval)

    threading.Thread(target=lus, daemon=True).start()


def _naar_datum(s):
    if not s or len(s) < 10:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
