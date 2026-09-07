"""Read-only server integration smoke client. Never prints credentials or tokens."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
import requests


def run(credentials_file):
    credentials = json.loads(Path(credentials_file).read_text())
    base = credentials["resource"]
    origin = urlsplit(base)
    if origin.scheme != "https" and not (
        origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Use HTTPS; HTTP is allowed only for local testing.")
    with requests.Session() as session:
        result = session.post(
            base + "oauth/token",
            auth=(credentials["client_id"], credentials["client_secret"]),
            data={
                "grant_type": "client_credentials",
                "scope": "catalog:read",
                "resource": base,
            },
            timeout=15,
            allow_redirects=False,
        )
        if result.status_code != 200:
            raise RuntimeError(f"Token request failed: HTTP {result.status_code}")
        token = result.json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        result = session.get(
            base + "catalogs", headers=headers, timeout=15, allow_redirects=False
        )
        result.raise_for_status()
        catalogs = result.json()["catalogs"]
        total = 0
        for catalog in catalogs:
            after = 0
            while True:
                result = session.get(
                    base + "catalogs/" + catalog["slug"] + "/recipes",
                    params={"after": after, "limit": 100},
                    headers=headers,
                    timeout=15,
                    allow_redirects=False,
                )
                result.raise_for_status()
                page = result.json()
                for recipe in page["results"]:
                    assert recipe["provenance"], "Attribution is required"
                total += len(page["results"])
                if page["next_after"] is None:
                    break
                after = page["next_after"]
        result = session.post(
            base + "oauth/revoke",
            auth=(credentials["client_id"], credentials["client_secret"]),
            data={"token": token},
            timeout=15,
            allow_redirects=False,
        )
        result.raise_for_status()
        print(
            json.dumps(
                {
                    "catalogs": len(catalogs),
                    "recipes_read": total,
                    "token_revoked": True,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("credentials_file")
    try:
        run(parser.parse_args().credentials_file)
    except Exception as error:
        # Requests exceptions may embed URLs; credentials and provider bodies stay private.
        raise SystemExit(
            "Catalog smoke failed ("
            + type(error).__name__
            + "). Check configuration and audit records."
        )
