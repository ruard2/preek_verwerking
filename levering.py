"""Weekboekje als e-mail opmaken en naar inschrijvers versturen (via Brevo)."""

from xml.sax.saxutils import escape

import brevo
import render
import subscribers
import ui_i18n


def _dag_blok(L, dag, nummer, accent="#2c5f2d"):
    return (
        f'<h3 style="color:{accent};margin:1.4em 0 .3em">'
        f'{escape(L["dag"])} {nummer} – {escape(dag.get("titel", ""))}</h3>'
        f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
        f'letter-spacing:.05em;margin:.6em 0 .1em">{escape(L["bijbeltekst"])}</p>'
        f'<p style="margin:.1em 0"><em>{escape(dag.get("bijbeltekst", ""))}</em></p>'
        f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
        f'letter-spacing:.05em;margin:.7em 0 .1em">{escape(L["gedachte"])}</p>'
        f'<p style="margin:.1em 0">{escape(dag.get("gedachte", ""))}</p>'
        f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
        f'letter-spacing:.05em;margin:.7em 0 .1em">{escape(L["vraag"])}</p>'
        f'<p style="margin:.1em 0">{escape(dag.get("vraag_volwassenen", ""))}</p>'
        f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
        f'letter-spacing:.05em;margin:.7em 0 .1em">{escape(L["vraag_kinderen"])}</p>'
        f'<p style="margin:.1em 0">{escape(dag.get("vraag_kinderen", ""))}</p>'
    )


def _nabespreking_blok(L, nabespreking, accent):
    """HTML voor de nabespreekvragen (hoofd/hart/handen) in de mail."""
    uit = (
        f'<h3 style="color:{accent};margin:1.4em 0 .3em">{escape(L["nabespreking"])}</h3>'
    )
    for cat in ("hoofd", "hart", "handen"):
        vragen = (nabespreking or {}).get(cat) or []
        if not vragen:
            continue
        uit += (
            f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
            f'letter-spacing:.05em;margin:.7em 0 .1em">{escape(L[cat])}</p><ul style="margin:.2em 0">'
        )
        uit += "".join(f'<li style="margin:.2em 0">{escape(v)}</li>' for v in vragen)
        uit += "</ul>"
    return uit


def _transcript_blok(L, transcript, accent):
    """HTML voor de volledige preektekst in de mail (alinea's)."""
    alineas = [a.strip() for a in (transcript or "").split("\n") if a.strip()]
    kop = f'<h3 style="color:{accent};margin:1.4em 0 .3em">{escape(L["transcript"])}</h3>'
    return kop + "".join(f'<p style="margin:.5em 0">{escape(a)}</p>' for a in alineas)


def bouw_email(data, kerk_naam, base_url, voorkeur_token, alleen_dag=None,
               communicatie_taal="nl", ai_disclaimer=True, logo_url=None,
               accent="#2c5f2d"):
    """Geef (onderwerp, html) voor het weekboekje of één dag (0-geïndexeerd)."""
    accent = accent or "#2c5f2d"
    L = render.labels(data.get("taal"))
    titel = data.get("titel", L["week"])
    dagen = data.get("dagen", [])

    kop = ""
    if logo_url:
        kop += (
            f'<div style="text-align:center;margin:0 0 1.2em">'
            f'<img src="{escape(logo_url)}" alt="{escape(kerk_naam)}" '
            f'style="max-height:64px;max-width:220px"></div>'
        )
    kop += f'<h2 style="color:{accent};margin:0 0 .2em">{escape(titel)}</h2>'
    onder = []
    if data.get("bijbelgedeelte"):
        onder.append(f"{escape(L['bijbelgedeelte'])}: {escape(data['bijbelgedeelte'])}")
    if data.get("voorganger"):
        onder.append(f"{escape(L['voorganger'])}: {escape(data['voorganger'])}")
    kop += f'<p style="color:#6b6b64;font-size:13px">{" · ".join(onder)}</p>'

    if alleen_dag is not None and 0 <= alleen_dag < len(dagen):
        onderwerp = f"{titel} — {L['dag']} {alleen_dag + 1}"
        body = kop + _dag_blok(L, dagen[alleen_dag], alleen_dag + 1, accent)
    else:
        onderwerp = titel
        body = kop
        typen = render.gekozen_typen(data)
        if ("dagstukjes" in typen or "preeksamenvatting" in typen) and data.get("samenvatting"):
            body += (
                f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
                f'letter-spacing:.05em;margin:1em 0 .1em">{escape(L["samenvatting"])}</p>'
                f'<p>{escape(data.get("samenvatting", ""))}</p>'
            )
        if "dagstukjes" in typen:
            for i, dag in enumerate(dagen):
                body += _dag_blok(L, dag, i + 1, accent)
        if "nabespreking" in typen and data.get("nabespreking"):
            body += _nabespreking_blok(L, data["nabespreking"], accent)
        if "preektranscript" in typen and data.get("preektranscript"):
            body += _transcript_blok(L, data["preektranscript"], accent)

    afmeld = f"{base_url}/afmelden?token={voorkeur_token}"
    voorkeur = f"{base_url}/voorkeuren?token={voorkeur_token}"
    C = ui_i18n.messages(communicatie_taal)
    disclaimer = (
        f'<p style="color:#a0a099;font-size:11px;margin:.4em 0 0">'
        f'{escape(C.get("ai_disclaimer", ""))}</p>' if ai_disclaimer else ""
    )
    voettekst = (
        f'<hr style="border:none;border-top:1px solid #e2e2dd;margin:2em 0 1em">'
        f'<p style="color:#8a8a80;font-size:12px">'
        f'{escape(C["receiving"].format(church=kerk_naam))} '
        f'<a href="{voorkeur}" style="color:{accent}">{escape(C["preferences"])}</a> · '
        f'<a href="{afmeld}" style="color:{accent}">{escape(C["unsubscribe"])}</a></p>'
        f'{disclaimer}'
    )
    html = (
        '<div style="font-family:Georgia,serif;max-width:640px;margin:0 auto;'
        f'color:#23231f;line-height:1.55">{body}{voettekst}</div>'
    )
    return onderwerp, html


def verstuur_een(kerk, data, base_url, sub, alleen_dag=None):
    """Bezorg één overdenking bij één inschrijver via het gekozen kanaal
    (e-mail en/of push)."""
    kanaal = getattr(sub, "kanaal", "email") or "email"
    if kanaal in ("email", "beide"):
        logo_url = f"{base_url}/logo/{kerk.id}" if getattr(kerk, "logo", "") else None
        onderwerp, html = bouw_email(
            data, kerk.naam or "AfterSermon", base_url, sub.voorkeur_token, alleen_dag,
            kerk.communicatie_taal, getattr(kerk, "ai_disclaimer", True), logo_url,
            getattr(kerk, "accentkleur", None),
        )
        brevo.verzend(
            sub.email, onderwerp, html,
            van_naam=kerk.naam or None, antwoord_naar=kerk.email or None,
        )
    if kanaal in ("push", "beide") and getattr(sub, "push_abonnement", ""):
        _stuur_push(sub, data, alleen_dag)
    return True


def _stuur_push(sub, data, alleen_dag):
    import json

    import push

    titel = data.get("titel") or "Overdenking bij de preek"
    tekst = (data.get("samenvatting") or "")[:140]
    dagen = data.get("dagen") or []
    if alleen_dag is not None and 0 <= alleen_dag < len(dagen):
        d = dagen[alleen_dag]
        titel = f"{d.get('titel', '')}".strip() or titel
        tekst = (d.get("gedachte") or "")[:140]
    try:
        push.stuur(json.loads(sub.push_abonnement), titel, tekst)
    except Exception:  # noqa: BLE001 — push-fout mag de bezorging niet breken
        pass


def verstuur_weekboekje(db, kerk, data, base_url, dagdeel=""):
    """Stuur het volledige weekboekje handmatig naar alle bevestigde inschrijvers.

    Met `dagdeel` ("ochtend"/"avond") worden alleen inschrijvers meegenomen die
    dat dagdeel willen (of "beide"). Geeft het aantal verzonden mails terug.
    """
    verzonden = 0
    for sub in subscribers.lijst(db, kerk.id):
        if not sub.bevestigd:
            continue
        voorkeur = getattr(sub, "dienstvoorkeur", "beide") or "beide"
        if dagdeel and voorkeur != "beide" and voorkeur != dagdeel:
            continue
        verstuur_een(kerk, data, base_url, sub)
        verzonden += 1
    return verzonden
