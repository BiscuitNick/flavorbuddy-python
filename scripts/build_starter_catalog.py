"""Build a deterministic seed snapshot from an explicitly supplied local source checkout.

Never executes repository code. Markdown is parsed as text; remote content is not fetched.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

REPOSITORY = "https://github.com/ronaldl29/public-domain-recipes"
SITE = "https://publicdomainrecipes.com/"
EXCLUDED_IMAGES = json.loads(
    (Path(__file__).resolve().parent.parent / "data/starter/excluded-image-urls.json").read_text()
)
parser = MarkdownIt("commonmark", {"html": False})


def plain(node):
    # Preserve link destinations, since some recipes depend on another preparation.
    for link in node.find_all("a"):
        href = link.get("href", "")
        if href:
            link.replace_with(f"{link.get_text()} ({urljoin(SITE, href)})")
    return node.get_text(" ", strip=True)


def convert(path, revision):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("Missing YAML frontmatter")
    meta = yaml.safe_load(parts[1])
    soup = BeautifulSoup(parser.render(parts[2]), "html.parser")
    image = soup.find("img")
    content = dict(
        title=str(meta.get("title", "")).strip(),
        author=str(meta.get("author", "")),
        description="",
        total_time=None,
        yields="",
        source_url=urljoin(SITE, path.stem + "/"),
        image=urljoin(SITE, image["src"]) if image and image.get("src") else "",
        ingredients=[],
        instructions=[],
        notes="",
    )
    if content["image"] in EXCLUDED_IMAGES:
        content["image"] = ""
    section = "description"
    group = ""
    notes = []
    descriptions = []
    for node in soup.children:
        if not getattr(node, "name", None):
            continue
        if node.name in ("h1", "h2"):
            heading = plain(node).lower()
            section = (
                "ingredients"
                if "ingredient" in heading
                else "instructions"
                if any(
                    w in heading
                    for w in ("direction", "instruction", "preparation", "method")
                )
                else "notes"
            )
            group = ""
            if section == "notes":
                notes.append(plain(node))
        elif node.name in ("h3", "h4"):
            group = plain(node)
        elif node.name in ("ul", "ol"):
            for item in node.find_all("li", recursive=False):
                value = plain(item)
                if not value:
                    continue
                if section in ("ingredients", "instructions"):
                    content[section].append(f"{group}: {value}" if group else value)
                else:
                    match = re.search(r"Servings\s*:\s*(.+)", value, re.I)
                    if match:
                        content["yields"] = match.group(1)
                    else:
                        notes.append(value)
        else:
            value = plain(node)
            if value:
                if section == "description":
                    descriptions.append(value)
                elif section == "instructions":
                    content["instructions"].append(
                        f"{group}: {value}" if group else value
                    )
                else:
                    notes.append(value)
    content["description"] = "\n\n".join(descriptions)
    # Preserve source timing text; do not guess totals when prep/cook/rest overlap.
    content["notes"] = "\n\n".join(notes)
    return {
        "slug": path.stem,
        "content": content,
        "provenance": {
            "repository": REPOSITORY,
            "revision": revision,
            "path": "content/" + path.name,
            "source_url": content["source_url"],
            "license": "Unlicense",
            "license_url": REPOSITORY + "/blob/" + revision + "/LICENSE.md",
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "tags": meta.get("tags", []),
        },
        "source_markdown": raw,
    }


def main():
    args = argparse.ArgumentParser()
    args.add_argument("checkout", type=Path)
    args.add_argument(
        "--output", type=Path, default=Path("data/starter/public-domain-recipes.json")
    )
    args.add_argument("--limit", type=int, default=500)
    options = args.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(options.checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    # Use FlavorBuddy's actual save contract to validate every selected record.
    import os, sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from scrape_me.api.serializers import RecipeSerializer

    rows = []
    skipped = []
    paths = sorted(
        p
        for p in (options.checkout / "content").glob("*.md")
        if not p.name.startswith("_")
    )
    for path in paths:
        try:
            row = convert(path, revision)
            serializer = RecipeSerializer(data=row["content"])
            serializer.is_valid(raise_exception=True)
            row["content"] = dict(serializer.validated_data)
            rows.append(row)
        except Exception as exc:
            skipped.append({"path": path.name, "reason": str(exc)})
    result = {
        "repository": REPOSITORY,
        "revision": revision,
        "target": options.limit,
        "available": len(paths),
        "valid": len(rows),
        "selected": len(rows[: options.limit]),
        "skipped": skipped,
        "recipes": rows[: options.limit],
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "recipes"}, indent=2))


if __name__ == "__main__":
    main()
