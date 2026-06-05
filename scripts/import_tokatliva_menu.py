#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tokat Liva public menu importer.

Fetches category pages from tokatliva.com and writes a local JSON snapshot used
by the local menu clone page.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT_DIR / "web" / "data" / "tokatliva_menu.json"
SOURCE_BASE = "https://www.tokatliva.com"

CATEGORIES = [
    ("Başlangıç", 60),
    ("Yemek", 59),
    ("Tencere ve Fırın", 64),
    ("Soğuk İçecekler", 61),
    ("Sıcak İçecekler", 62),
    ("Baklavalar", 63),
    ("Süt Tatlıları", 67),
    ("Dondurma", 68),
]


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def text_from_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def parse_price(price_text: str) -> float:
    normalized = price_text.replace("TL", "").replace(".", "").replace(",", ".")
    normalized = re.sub(r"[^0-9.]", "", normalized)
    return float(normalized or 0)


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    return html.unescape(match.group(1).strip()) if match else ""


def parse_products(page_html: str) -> list[dict[str, object]]:
    blocks = re.findall(
        r'<div class="product-layout[^"]*".*?</div>\s*</div>\s*</div>\s*</div>',
        page_html,
        re.S,
    )
    products: list[dict[str, object]] = []

    for block in blocks:
        name_html = first_match(r'<div class="name">\s*<a[^>]*>(.*?)</a>', block)
        price_html = first_match(r'<span class="price-normal">(.*?)</span>', block)
        if not name_html or not price_html:
            continue

        image_url = first_match(r'<img[^>]+data-src="([^"]+)"', block)
        if not image_url:
            image_url = first_match(r'<img[^>]+src="([^"]+)"', block)

        products.append(
            {
                "name": text_from_html(name_html),
                "price": parse_price(text_from_html(price_html)),
                "price_text": text_from_html(price_html),
                "image_url": image_url,
                "source_url": first_match(r'<a href="([^"]+)" class="product-img', block),
            }
        )

    return products


def build_menu() -> dict[str, object]:
    categories = []
    for category_name, path_id in CATEGORIES:
        url = f"{SOURCE_BASE}/index.php?route=product/category&path={path_id}"
        page_html = fetch(url)
        title = text_from_html(first_match(r"<title>(.*?)</title>", page_html))
        categories.append(
            {
                "name": title or category_name,
                "path_id": path_id,
                "source_url": url,
                "items": parse_products(page_html),
            }
        )

    return {
        "source": SOURCE_BASE,
        "source_name": "Tokat Liva Restaurant",
        "fetched_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "categories": categories,
    }


def write_menu_txt(snapshot: dict[str, object], menu_file: Path) -> None:
    lines = []
    for category in snapshot["categories"]:
        for item in category["items"]:
            image_url = str(item.get("image_url", "")).replace(";", "")
            name = str(item.get("name", "")).replace(";", ",")
            price = float(item.get("price", 0))
            lines.append(f"{category['name']};{name};{price};0;0;0;0;{image_url};1\n")
    menu_file.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tokatliva.com menüsünü yerel JSON'a aktarır.")
    parser.add_argument(
        "--input",
        help="Web'den çekmek yerine mevcut JSON snapshot dosyasını kullan",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Yazılacak JSON dosyası")
    parser.add_argument(
        "--write-menu-txt",
        action="store_true",
        help="Ayrıca repo kökündeki menu.txt dosyasını aynı ürünlerle güncelle",
    )
    args = parser.parse_args()

    output = Path(args.output)
    if args.input:
        try:
            snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Menü snapshot okunamadı: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            snapshot = build_menu()
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"Menü alınamadı: {exc}", file=sys.stderr)
            return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.write_menu_txt:
        write_menu_txt(snapshot, ROOT_DIR / "menu.txt")

    item_count = sum(len(category["items"]) for category in snapshot["categories"])
    print(f"{len(snapshot['categories'])} kategori, {item_count} ürün yazıldı: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
