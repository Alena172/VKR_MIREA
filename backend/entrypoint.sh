#!/bin/sh
set -e
python - <<'EOF'
import os
import sqlalchemy

engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    alembic_version_exists = conn.execute(sqlalchemy.text(
        "SELECT to_regclass('public.alembic_version')"
    )).scalar()
    version = None
    if alembic_version_exists:
        version = conn.execute(sqlalchemy.text(
            "SELECT version_num FROM alembic_version WHERE version_num = '0013_shared_dictionary'"
        )).scalar()
    if version:
        user_vocabulary_exists = conn.execute(sqlalchemy.text(
            "SELECT to_regclass('public.user_vocabulary')"
        )).scalar()
        dictionary_entries_exists = conn.execute(sqlalchemy.text(
            "SELECT to_regclass('public.dictionary_entries')"
        )).scalar()
        if not user_vocabulary_exists or not dictionary_entries_exists:
            print("Detected incomplete 0013 migration — re-stamping to 0012")
            conn.execute(sqlalchemy.text(
                "UPDATE alembic_version SET version_num = '0012_rename_mistake_events_to_sense_error_events'"
            ))
            conn.commit()
EOF

python -m alembic upgrade head

UVICORN_RELOAD_FLAG=""
if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
    UVICORN_RELOAD_FLAG="--reload"
fi

WORKERS=${UVICORN_WORKERS:-4}
if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
    WORKERS=1
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers $WORKERS $UVICORN_RELOAD_FLAG
