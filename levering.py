"""Weekboekje als e-mail opmaken en naar inschrijvers versturen (via Brevo)."""

from xml.sax.saxutils import escape

import brevo
import render
import subscribers
import ui_i18n


def _dag_blok(L, dag, nummer):
    return (
        f'<h3 style="color:#2c5f2d;margin:1.4em 0 .3em">'
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


def bouw_email(data, kerk_naam, base_url, voorkeur_token, alleen_dag=None,
               communicatie_taal="nl", ai_disclaimer=True):
    """Geef (onderwerp, html) voor het weekboekje of één dag (0-geïndexeerd)."""
    L = render.labels(data.get("taal"))
    titel = data.get("titel", L["week"])
    dagen = data.get("dagen", [])

    kop = f'<h2 style="color:#2c5f2d;margin:0 0 .2em">{escape(titel)}</h2>'
    onder = []
    if data.get("bijbelgedeelte"):
        onder.append(f"{escape(L['bijbelgedeelte'])}: {escape(data['bijbelgedeelte'])}")
    if data.get("voorganger"):
        onder.append(f"{escape(L['voorganger'])}: {escape(data['voorganger'])}")
    kop += f'<p style="color:#6b6b64;font-size:13px">{" · ".join(onder)}</p>'

    if alleen_dag is not None and 0 <= alleen_dag < len(dagen):
        onderwerp = f"{titel} — {L['dag']} {alleen_dag + 1}"
        body = kop + _dag_blok(L, dagen[alleen_dag], alleen_dag + 1)
    else:
        onderwerp = titel
        body = kop
        body += (
            f'<p style="color:#6b6b64;font-size:12px;text-transform:uppercase;'
            f'letter-spacing:.05em;margin:1em 0 .1em">{escape(L["samenvatting"])}</p>'
            f'<p>{escape(data.get("samenvatting", ""))}</p>'
        )
        for i, dag in enumerate(dagen):
            body += _dag_blok(L, dag, i + 1)

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
        f'<a href="{voorkeur}" style="color:#2c5f2d">{escape(C["preferences"])}</a> · '
        f'<a href="{afmeld}" style="color:#2c5f2d">{escape(C["unsubscribe"])}</a></p>'
        f'{disclaimer}'
    )
    html = (
        '<div style="font-family:Georgia,serif;max-width:640px;margin:0 auto;'
        f'color:#23231f;line-height:1.55">{body}{voettekst}</div>'
    )
    return onderwerp, html


def verstuur_een(kerk, data, base_url, sub, alleen_dag=None):
    """Stuur één e-mail (heel boekje of één dag) naar één inschrijver."""
    onderwerp, html = bouw_email(
        data, kerk.naam or "AfterSermon", base_url, sub.voorkeur_token, alleen_dag,
        kerk.communicatie_taal, getattr(kerk, "ai_disclaimer", True),
    )
    return brevo.verzend(
        sub.email, onderwerp, html,
        van_naam=kerk.naam or None, antwoord_naar=kerk.email or None,
    )


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
