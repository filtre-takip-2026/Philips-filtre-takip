import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PRODUCT_URL = (
    "https://www.phaksesuar.com/"
    "philips-fy3430/30-nano-koruma-filtresi"
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def send_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("Telegram mesajı gönderilemedi.")


def check_stock():
    response = requests.get(
        PRODUCT_URL, headers=HEADERS, timeout=25
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Önce ürünün yapılandırılmış stok bilgisini kontrol et.
    for script in soup.find_all(
        "script", type="application/ld+json"
    ):
        try:
            data = json.loads(script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        nodes = data if isinstance(data, list) else [data]

        for node in nodes:
            if not isinstance(node, dict):
                continue

            offers = node.get("offers", {})
            if isinstance(offers, dict):
                offers = [offers]
            if not isinstance(offers, list):
                continue

            for offer in offers:
                if not isinstance(offer, dict):
                    continue

                availability = str(
                    offer.get("availability", "")
                ).lower()

                if "instock" in availability:
                    return "available"

                if any(word in availability for word in (
                    "outofstock", "soldout", "discontinued"
                )):
                    return "unavailable"

    # Yapılandırılmış bilgi yoksa sayfadaki metni incele.
    for tag in soup(
        ["script", "style", "noscript", "svg"]
    ):
        tag.decompose()

    text = re.sub(
        r"\s+", " ", soup.get_text(" ", strip=True)
    ).lower()

    if any(word in text for word in (
        "gelince haber ver", "stokta yok", "tükendi"
    )):
        return "unavailable"

    if (
        "fy3430/30" in text
        and any(word in text for word in (
            "sepete ekle", "satın al"
        ))
    ):
        return "available"

    return "unknown"


def main():
    try:
        state = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError):
        state = {"status": "unknown"}

    previous = state.get("status", "unknown")
    current = check_stock()

    print(f"Önceki durum: {previous}; yeni durum: {current}")

    if current == "available" and previous != "available":
        send_message(
            "🎉 Philips FY3430/30 filtresi stokta olabilir!\n"
            "Satın almadan önce sayfayı kontrol et:\n"
            + PRODUCT_URL
        )

    if current != "unknown":
        STATE_FILE.write_text(
            json.dumps({"status": current}),
            encoding="utf-8",
        )
    elif not STATE_FILE.exists():
        STATE_FILE.write_text(
            json.dumps({"status": "unknown"}),
            encoding="utf-8",
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Kontrol hatası: {error}", file=sys.stderr)
        sys.exit(1)
      
