"""Pure planningslogica — deterministisch, geen mocks nodig."""

from datetime import date, datetime

import automatisering as a


def test_komende_maandag():
    # zondag 2026-07-26 -> eerstvolgende maandag 2026-07-27
    assert a.komende_maandag(date(2026, 7, 26)) == date(2026, 7, 27)
    # maandag -> de MAANDAG erna (nooit dezelfde dag)
    assert a.komende_maandag(date(2026, 7, 27)) == date(2026, 8, 3)


def test_parse_tijd():
    assert a.parse_tijd("07:30").hour == 7
    assert a.parse_tijd("bogus").hour == 7  # veilige terugval


class _Kerk:
    verzend_dag = 0  # maandag
    verzend_tijd = "08:00"


class _Sub:
    def __init__(self, frequentie):
        self.frequentie = frequentie


def test_wekelijks_een_moment():
    ws = date(2026, 7, 27)  # maandag
    momenten = a.geplande_momenten(ws, _Kerk(), _Sub("wekelijks"))
    assert len(momenten) == 1
    dag, moment = momenten[0]
    assert dag == 0
    assert moment == datetime(2026, 7, 27, 8, 0)


def test_dagelijks_zeven_momenten():
    ws = date(2026, 7, 27)
    momenten = a.geplande_momenten(ws, _Kerk(), _Sub("dagelijks"))
    assert [d for d, _ in momenten] == [1, 2, 3, 4, 5, 6, 7]
    # dag 7 valt op de zondag erna
    assert momenten[-1][1] == datetime(2026, 8, 2, 8, 0)


def test_due_alleen_verstreken_binnen_grace():
    ws = date(2026, 7, 27)
    nu = datetime(2026, 7, 27, 9, 0)  # ná 08:00 op maandag
    due = a.due_momenten(ws, _Kerk(), _Sub("wekelijks"), nu)
    assert len(due) == 1
    # ruim vóór het moment: nog niets verschuldigd
    assert a.due_momenten(ws, _Kerk(), _Sub("wekelijks"), datetime(2026, 7, 27, 7, 0)) == []
    # veel te laat (buiten grace): niet meer versturen
    laat = datetime(2026, 8, 20, 9, 0)
    assert a.due_momenten(ws, _Kerk(), _Sub("wekelijks"), laat) == []
