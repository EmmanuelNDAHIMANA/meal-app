# Project M&E Data Platform

A Streamlit app with login authentication for recording project data into a
MySQL database. Nine data tables, each with **single-record entry**, **bulk
Excel upload with a downloadable template**, and a **dashboard** filtered by
Project / Implementer / Intervention.

Dropdowns are driven by your validated reference data, bundled in `reference/`:

| File | Used for | Size |
|---|---|---|
| `reference/Location.xlsx` | District → Sector → Cell → Village | 14,842 rows · 30 districts · 387 sectors · 1,467 cells · 6,621 villages |
| `reference/Interventions.xlsx` | Implementer → Intervention | 65 rows · 6 implementers |
| `reference/Trees.xlsx` | Tree Orgine → Tree Type → Tree species | **optional, not supplied** |

---

## ⚠️ Rotate your database password

The Aiven password was pasted in plaintext in chat. **Rotate it in the Aiven
console before putting real data in this.** The app never hardcodes
credentials — it reads them from `.streamlit/secrets.toml` or environment
variables, and `secrets.toml` is git-ignored.

---

## Setup

```bash
# 1. install
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. credentials
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#    then edit .streamlit/secrets.toml and put your real DB_PASSWORD in it

# 3. create the tables  (run from THIS folder)
python create_tables.py

# 4. create your login
python create_admin.py

# 5. run
streamlit run app.py
```

There is **no default username or password.** Step 4 is where you choose
them. Once signed in as admin you can add more users, reset passwords, and
disable accounts from the home page.

### If you get `Access denied ... (using password: NO)`

That means `DB_PASSWORD` was not found — the app fell back to an empty
password. Check, in order:

1. The file is `.streamlit/secrets.toml`, **not** `secrets.toml.example`.
2. You are running the command from the folder that contains `app.py`.
3. Verify what's being picked up (this does not print the password):
   ```bash
   python -c "import config; print(config.DB_HOST, config.DB_USER, 'password set:', bool(config.DB_PASSWORD))"
   ```
4. If it says `password set: True` but access is still denied, the password
   itself is wrong, or your IP is not in the Aiven service's allowed-IP list.

---

## Using the app

Each table page has three tabs.

**📝 Submit one record** — a two-column form. Dropdowns cascade live:
choosing an Implementer filters Intervention; District filters Sector, which
filters Cell, which filters Village. Required fields are marked `*` and are
checked before anything is written.

**📥 Bulk upload** — download the table's Excel template, fill it, upload it.
The template contains:

- `READ_ME` — filling instructions
- `Data` — the sheet you fill in. Headers match the spec exactly. Red headers
  are required, blue are optional. In-cell dropdowns on Project, Implementer,
  District, Gender, Youth. **Intervention cascades off the Implementer cell in
  the same row** (via named ranges + `INDIRECT`).
- `Lists` — the option lists backing those dropdowns
- `Location_Lookup` — all 14,842 District/Sector/Cell/Village rows, filterable
- `Intervention_Lookup` — all Implementer/Intervention pairs

On upload every row is validated. Valid rows are previewed before you confirm
the insert; invalid rows are **never inserted** and are listed with the exact
reason, downloadable as CSV. Example rejections:

```
Project 'XXXX' is not one of TREPA, COMBIO, AREECA, DESIRA
Intervention 'Silvo-pastural' does not belong to Implementer 'Enabel'
Location 'Nyarugenge > Gitega > Akabahizi > Kigali' is not a valid combination
'Number of persons in HH' invalid int value ('many')
```

Sector, Cell and Village are typed rather than dropdowns in Excel (a
four-level cascade would need ~1,900 named ranges and breaks in some Excel
builds), but they are fully validated on upload against `Location_Lookup`.

**📊 Dashboard** — Project / Implementer / Intervention slicers, headline
metrics, charts by Implementer, Project, Intervention, District and Gender,
plus the filtered record table and a CSV export.

---

## Tables created

`tree_plantation`, `beneficiaries`, `bso`, `silvo`, `af_demo`, `activities`,
`indicators`, `trainings`, `jobs_created`, plus `users`.

Every data table gets an auto-increment `id`, and audit columns `created_by`,
`created_at`, `source` (`manual` or `bulk`), plus indexes on `project`,
`implementer`, `intervention`, `district`.

---

## Adding tree species dropdowns

Tree Orgine / Tree Type / Tree species are currently **free text**, because no
tree reference file was supplied. To turn them into cascading dropdowns, drop
a file at `reference/Trees.xlsx` with exactly these three columns:

| Tree Orgine | Tree Type | Tree species |
|---|---|---|

Restart the app. The forms, the Excel template dropdowns, a `Tree_Lookup`
sheet, and upload validation all pick it up automatically — no code change.

---

## Project layout

```
app.py                 home: connection status, record counts, user admin
auth.py                bcrypt login, user management
config.py              credentials (from secrets/env) + reference paths
db.py                  SQLAlchemy engine + query helpers
schemas.py             ← single source of truth for all 9 tables
reference_data.py      loads Location/Interventions/Trees, cascade + validation
templates.py           builds the Excel templates with dropdowns
forms.py               shared form / upload / dashboard engine
create_tables.py       one-off: create all tables
create_admin.py        one-off: create your first admin
pages/1..9_*.py        one page per table (each ~25 lines, no duplicated logic)
reference/             your bundled validated Excel data
```

**To change a table's columns, edit `schemas.py` only.** The form, the Excel
template, the upload validator, the `CREATE TABLE` statement and the dashboard
all read from that one definition.

---

## Notes on the spec

- Column labels are kept exactly as you wrote them (including `Tree Orgine`,
  `Owner's Name (Invidual/FFS/Group)`, `Gender (Male &Female)`) so your
  existing spreadsheets match the template headers.
- `Activities`, `Indicators` and `Trainings` have Implementer but no
  Intervention column, per your spec. `Tree plantation` and `Jobs_created`
  have District/Sector/Cell but no Village, also per your spec.
- `Tree plantation` uses "Tree Category" where the other tables use "Tree
  Orgine"; both validate against the same tree reference if you supply one.
