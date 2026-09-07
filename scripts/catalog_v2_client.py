"""Bounded search → choose → UUID detail smoke; never logs credentials or provider bodies."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
import requests
from jsonschema import Draft202012Validator, FormatChecker


def run(credentials_file, catalog, query="", cloud_run=False):
    credentials = json.loads(Path(credentials_file).read_text())
    resource = urlsplit(credentials["resource"])
    if resource.scheme != "https" and not (
        resource.scheme == "http" and resource.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("HTTPS required outside loopback.")
    if (
        resource.username
        or resource.password
        or resource.query
        or resource.fragment
        or not re.fullmatch(r"[A-Za-z0-9_-]+", catalog)
    ):
        raise ValueError("Invalid origin or catalog.")
    origin = f"{resource.scheme}://{resource.netloc}"
    base = origin + "/api/integrations/v2/"
    oauth = origin + "/api/integrations/v1/oauth/"
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "docs/api/RecipeDocumentV1.schema.json"
        ).read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    with requests.Session() as session:
        if cloud_run:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"], text=True
            ).strip()
            session.headers["X-Serverless-Authorization"] = "Bearer " + token
        auth = (credentials["client_id"], credentials["client_secret"])
        response = session.post(
            oauth + "token",
            auth=auth,
            data={
                "grant_type": "client_credentials",
                "scope": "catalog:read",
                "resource": base,
            },
            timeout=30,
            allow_redirects=False,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        try:
            response = session.get(
                base + "catalogs/" + catalog + "/recipes",
                params={"q": query, "limit": 12},
                headers=headers,
                timeout=30,
                allow_redirects=False,
            )
            response.raise_for_status()
            results = response.json()["results"]
            if not results:
                raise ValueError("Search returned no candidates.")
            recipe_id = results[0]["recipe_id"]
            response = session.get(
                base + "recipes/" + recipe_id,
                headers=headers,
                timeout=30,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
            validator.validate(data["document"])
            assert data["document"]["recipe_id"] == recipe_id
            assert data["status"]["availability"] == "available"
        finally:
            revoked = session.post(
                oauth + "revoke",
                auth=auth,
                data={"token": token},
                timeout=30,
                allow_redirects=False,
            )
            revoked.raise_for_status()
        denied = session.get(
            base + "recipes/" + recipe_id,
            headers=headers,
            timeout=30,
            allow_redirects=False,
        )
        assert denied.status_code == 401
        print(
            json.dumps(
                {
                    "candidates": len(results),
                    "document_valid": True,
                    "token_revoked": True,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("credentials_file")
    parser.add_argument("catalog")
    parser.add_argument("--query", default="")
    parser.add_argument("--cloud-run", action="store_true")
    try:
        args = parser.parse_args()
        run(args.credentials_file, args.catalog, args.query, args.cloud_run)
    except Exception as error:
        raise SystemExit(
            f"V2 smoke failed ({type(error).__name__}); check configuration and request audit."
        )
