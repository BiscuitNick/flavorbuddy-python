"""Synthetic two-user HTTPS release smoke. Credentials stay in a private local file."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import uuid
from urllib.parse import urlsplit
import requests
from PIL import Image


def run(origin, evidence_file, verify_only=False):
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ValueError("Use the exact HTTPS staging origin.")
    origin = origin.rstrip("/")
    p = Path(evidence_file)
    identity = subprocess.check_output(
        ["gcloud", "auth", "print-identity-token"], text=True
    ).strip()
    data = (
        json.loads(p.read_text()) if p.exists() else {"origin": origin, "accounts": []}
    )
    if data["origin"] != origin:
        raise ValueError("Evidence belongs to another environment.")
    if not data["accounts"]:
        for role in ("alice", "bob"):
            data["accounts"].append(
                {
                    "email": f"release-{role}-{uuid.uuid4().hex[:10]}@example.com",
                    "password": secrets.token_urlsafe(32),
                }
            )
    os.umask(0o077)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    p.chmod(0o600)
    sessions = []

    def request(session, method, path, expected=200, **kwargs):
        response = session.request(
            method, origin + path, timeout=60, allow_redirects=False, **kwargs
        )
        if response.status_code != expected:
            raise RuntimeError(
                f"{method} {path.split('?')[0]} returned {response.status_code}; expected {expected}"
            )
        return response

    for account in data["accounts"]:
        s = requests.Session()
        s.headers.update(
            {
                "X-Serverless-Authorization": "Bearer " + identity,
                "Origin": origin,
                "Referer": origin + "/",
            }
        )
        me = request(s, "GET", "/api/v1/me").json()
        s.headers["X-CSRFToken"] = me["csrf_token"]
        action = "login" if account.get("registered") or verify_only else "register"
        request(
            s,
            "POST",
            "/api/v1/auth/" + action,
            json={"email": account["email"], "password": account["password"]},
        )
        account["registered"] = True
        p.write_text(json.dumps(data))
        me = request(s, "GET", "/api/v1/me").json()
        s.headers["X-CSRFToken"] = me["csrf_token"]
        assert all(
            cookie.secure
            for cookie in s.cookies
            if cookie.name in ("sessionid", "csrftoken")
        )
        sessions.append(s)
    a, b = sessions
    request(a, "GET", "/health/ready")
    assert requests.get(
        origin + "/health/ready", timeout=30, allow_redirects=False
    ).status_code in (401, 403)
    if not verify_only and not data.get("recipe_id"):
        preview = request(
            a,
            "POST",
            "/api/v1/imports",
            expected=201,
            json={"key": str(uuid.uuid4()), "mode": "manual", "input": ""},
        ).json()
        assert preview["state"] == "ready"
        recipe = request(
            a,
            "POST",
            "/api/v1/recipes",
            expected=201,
            json={
                "import_id": preview["id"],
                "title": "Release smoke pasta",
                "ingredients": ["200g pasta", "Salt"],
                "instructions": ["Boil water.", "Cook pasta."],
                "notes": "Synthetic private note",
                "source_url": "https://example.com/release-pasta",
            },
        ).json()
        recipe = request(
            a,
            "POST",
            f"/api/v1/recipes/{recipe['id']}/finalize",
            json={"version": recipe["version"]},
        ).json()
        recipe = request(
            a,
            "POST",
            f"/api/v1/recipes/{recipe['id']}/cook",
            json={
                "key": str(uuid.uuid4()),
                "version": recipe["version"],
                "notes": "Synthetic private cooked note",
            },
        ).json()
        other = request(
            b,
            "POST",
            "/api/v1/recipes",
            expected=201,
            json={
                "title": "Bob independent pasta",
                "ingredients": ["Pasta"],
                "instructions": ["Boil."],
                "source_url": "https://example.com/release-pasta",
            },
        ).json()
        pantry = request(
            a,
            "POST",
            "/api/v1/pantry",
            expected=201,
            json={"name": "Pasta", "location": "Pantry", "quantity": "one bag"},
        ).json()
        data.update(
            {
                "recipe_id": recipe["id"],
                "other_recipe_id": other["id"],
                "recipe_uuid": recipe["public_id"],
                "pantry_id": pantry["id"],
            }
        )
        p.write_text(json.dumps(data))
    if not verify_only and not data.get("photo_id"):
        image = io.BytesIO()
        Image.new("RGB", (32, 32), (40, 120, 60)).save(image, "PNG")
        photo = request(
            a,
            "POST",
            f"/api/v1/recipes/{data['recipe_id']}/photos",
            expected=201,
            files={"photo": ("synthetic.png", image.getvalue(), "image/png")},
            data={"kind": "cover"},
        ).json()
        data["photo_id"] = photo["id"]
        data["photo_sha256"] = hashlib.sha256(
            request(a, "GET", f"/api/v1/photos/{photo['id']}/content").content
        ).hexdigest()
        p.write_text(json.dumps(data))
    request(b, "GET", f"/api/v1/recipes/{data['recipe_id']}", expected=404)
    request(a, "GET", f"/api/v1/recipes/{data['other_recipe_id']}", expected=404)
    request(b, "GET", f"/api/v1/photos/{data['photo_id']}/content", expected=404)
    request(
        b,
        "PATCH",
        f"/api/v1/pantry/{data['pantry_id']}",
        expected=404,
        json={"version": 1, "quantity": "changed"},
    )
    recipes = request(a, "GET", "/api/v1/recipes/export").json()["recipes"]
    assert len(recipes) == 1 and recipes[0]["public_id"] == data["recipe_uuid"]
    assert request(b, "GET", "/api/v1/pantry").json()["items"] == []
    image = request(a, "GET", f"/api/v1/photos/{data['photo_id']}/content")
    assert image.headers["Cache-Control"] == "private, no-store"
    assert hashlib.sha256(image.content).hexdigest() == data["photo_sha256"]
    Image.open(io.BytesIO(image.content)).load()
    missing = requests.Session()
    missing.headers["X-Serverless-Authorization"] = "Bearer " + identity
    request(
        missing,
        "POST",
        "/api/v1/auth/login",
        expected=403,
        json={
            "email": data["accounts"][0]["email"],
            "password": data["accounts"][0]["password"],
        },
    )
    print(
        json.dumps(
            {
                "https": True,
                "anonymous_denied": True,
                "two_user_isolation": True,
                "manual_import_finalize_cook": True,
                "private_gcs_photo": True,
                "pantry_isolation": True,
                "csrf_enforced": True,
                "recovery_available": me["recovery_available"],
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("origin")
    p.add_argument("evidence_file")
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    run(args.origin, args.evidence_file, args.verify_only)
