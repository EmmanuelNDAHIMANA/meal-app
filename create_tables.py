"""
Creates the `users` table and all nine data tables.

    python create_tables.py

Safe to re-run: uses CREATE TABLE IF NOT EXISTS.
"""
from sqlalchemy import text

import db
import schemas

USERS_SQL = """
CREATE TABLE IF NOT EXISTS `users` (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(150) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'user',
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

REPORTS_SQL = """
CREATE TABLE IF NOT EXISTS `reports` (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    title             VARCHAR(255),
    stored_filename   VARCHAR(255) NOT NULL UNIQUE,
    original_filename VARCHAR(255) NOT NULL,
    uploaded_by       VARCHAR(100),
    uploaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_reports_uploaded_by` (`uploaded_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def build_sql(table_key: str) -> str:
    cfg = schemas.TABLES[table_key]
    seen, cols = set(), []
    for fl in cfg["fields"]:
        if fl["col"] in seen:
            continue
        seen.add(fl["col"])
        cols.append(f"    `{fl['col']}` {fl['sql']}")
    body = ",\n".join(cols)
    idx = []
    for c in ("project", "implementer", "intervention", "district"):
        if c in seen:
            idx.append(f",\n    INDEX `idx_{cfg['table']}_{c}` (`{c}`)")
    return f"""
CREATE TABLE IF NOT EXISTS `{cfg['table']}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
{body},
    created_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source     VARCHAR(20) DEFAULT 'manual'{''.join(idx)}
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def main():
    engine = db.get_engine()
    with engine.begin() as conn:
        print("→ users")
        conn.execute(text(USERS_SQL))
        print("→ reports")
        conn.execute(text(REPORTS_SQL))
        for key in schemas.TABLE_ORDER:
            print(f"→ {schemas.TABLES[key]['table']}")
            conn.execute(text(build_sql(key)))
    print("\nAll tables created (or already present).")
    print("Next: python create_admin.py")


if __name__ == "__main__":
    main()
