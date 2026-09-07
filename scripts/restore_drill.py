"""Local Compose-only restore rehearsal using synthetic data and disposable databases."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from config import settings
import psycopg2
from psycopg2 import sql

suffix = uuid.uuid4().hex[:10]
source, target = f"fb_drill_source_{suffix}", f"fb_drill_restore_{suffix}"
config = settings.DATABASES["default"]
admin = psycopg2.connect(
    dbname="postgres",
    user=config["USER"],
    password=config["PASSWORD"],
    host=config["HOST"],
    port=config["PORT"],
)
admin.autocommit = True
started = time.monotonic()


def run_python(database, code):
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**os.environ, "POSTGRES_DB": database},
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


try:
    for database in (source, target):
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=ROOT,
        env={**os.environ, "POSTGRES_DB": source},
        check=True,
        stdout=subprocess.DEVNULL,
    )
    run_python(
        source,
        """import django; django.setup()
from django.contrib.auth import get_user_model
from scrape_me.models import Recipe
U=get_user_model()
a=U.objects.create_user('restore-alice'); b=U.objects.create_user('restore-bob')
Recipe.objects.create(owner=a,title='Alice pasta',ingredients=['Pasta'],instructions=['Boil.'],notes='Private Alice note',source_url='https://example.com/pasta')
Recipe.objects.create(owner=b,title='Bob pasta',ingredients=['Pasta'],instructions=['Boil.'],notes='Private Bob note',source_url='https://example.com/pasta')
Recipe.objects.create(title='Legacy',ingredients=['Salt'])
""",
    )
    with tempfile.TemporaryFile() as backup:
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                config["USER"],
                "-d",
                source,
                "-Fc",
            ],
            cwd=ROOT,
            stdout=backup,
            check=True,
        )
        backup.seek(0)
        restore_started = time.monotonic()
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "pg_restore",
                "--no-owner",
                "-U",
                config["USER"],
                "-d",
                target,
            ],
            cwd=ROOT,
            stdin=backup,
            check=True,
        )
        restore_seconds = time.monotonic() - restore_started
    verified = run_python(
        target,
        """import django; django.setup()
from django.contrib.auth import get_user_model
from scrape_me.models import Recipe
from rest_framework.test import APIClient
assert Recipe.objects.count()==3
c=APIClient()
for name,title in [('restore-alice','Alice pasta'),('restore-bob','Bob pasta')]:
 c.force_authenticate(get_user_model().objects.get(username=name))
 data=c.get('/api/v1/recipes/export').json()['recipes']
 assert len(data)==1 and data[0]['title']==title
assert Recipe.objects.filter(owner=None,title='Legacy').exists()
print('3 recipes, 2 independent owners, legacy row, scoped exports verified')
""",
    )
    print(
        json.dumps(
            {
                "restore_seconds": round(restore_seconds, 3),
                "total_seconds": round(time.monotonic() - started, 3),
                "verification": verified,
            }
        )
    )
finally:
    for database in (source, target):
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )
    admin.close()
