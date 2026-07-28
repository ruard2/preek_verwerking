# Databasemigraties

Beleid voor schema-wijzigingen aan de database (SQLite lokaal, Postgres op Railway).

## Wat er automatisch gebeurt (veilig, bij elke start)

`db.init_db()` draait bij het opstarten en doet twee dingen die **nooit de
app-start mogen breken** (alles is idempotent en per-stap afgeschermd met
try/except + logging):

1. `Base.metadata.create_all()` — maakt **ontbrekende tabellen** aan.
2. `_voeg_ontbrekende_kolommen_toe()` — voegt **ontbrekende kolommen** toe aan
   bestaande tabellen (ADD COLUMN met de model-default).

Dit dekt de veruit meest voorkomende wijziging tijdens deze fase: een nieuw veld
of een nieuwe tabel. Een mislukte stap wordt gelogd en overgeslagen, zodat de
app blijft draaien.

## Wat je NIET automatisch mag doen

De auto-stap kan **alleen toevoegen**. Voor deze wijzigingen is een echte
migratie nodig (en handmatige controle):

- een kolom **hernoemen** of **verwijderen**;
- een **type of constraint** wijzigen;
- **data** verplaatsen/omzetten;
- een kolom `NOT NULL` maken op een bestaande, gevulde tabel.

Doe zulke wijzigingen bewust en getest — bij voorkeur met **Alembic**:

```bash
pip install alembic
alembic init alembic          # eenmalig; laat env.py wijzen naar db.Base.metadata en db.DATABASE_URL
alembic revision --autogenerate -m "omschrijving"
# controleer het gegenereerde script HANDMATIG (autogenerate mist renames/data)
alembic upgrade head
```

Voer migraties uit als een **bewuste, aparte stap** (niet automatisch bij het
opstarten), zodat een mislukte migratie de live-app niet plat legt. Test elke
migratie eerst tegen een kopie van de Postgres-database.
