#!/usr/bin/env python3
"""
Genera un feed RSS non ufficiale a partire da due pagine di elenco del sito
della Prefettura di Mantova:

    https://prefettura.interno.gov.it/it/prefetture/mantova/notizie
    https://prefettura.interno.gov.it/it/prefetture/mantova/evidenza/comunicati-stampa

Il sito e' un portale Drupal (schema "Designers Italia") con URL puliti.
Le pagine di dettaglio sono state osservate sotto DUE prefissi diversi:

    https://prefettura.interno.gov.it/it/prefetture/mantova/notizie/<slug>
    https://prefettura.interno.gov.it/it/prefetture/mantova/comunicati-stampa/<slug>

IMPORTANTE: lo stesso comunicato puo' essere raggiungibile con lo stesso
<slug> sotto entrambi i prefissi (alias Drupal). Per questo la deduplica non
avviene per URL esatto ma per <slug> (vedi `extract_slug`), cosi' da non
pubblicare due volte lo stesso comunicato nel feed.

Lo script:
  1. scarica entrambe le pagine di elenco
  2. individua ogni comunicato tramite i link che puntano al dettaglio
     (path che termina con "/notizie/<slug>" oppure
     "/comunicati-stampa/<slug>")
  3. deduplica i candidati per slug (tenendo il primo URL incontrato)
  4. per ogni slug nuovo (non gia' presente nel feed esistente) scarica la
     pagina di dettaglio per estrarre titolo, data e descrizione con
     maggiore affidabilita' rispetto alla sola pagina di elenco
  5. unisce i nuovi elementi con quelli gia' presenti in docs/feed.xml
     (se esiste), deduplica per slug, ordina per data decrescente e
     mantiene al massimo MAX_ITEMS elementi
  6. scrive docs/feed.xml (RSS 2.0 valido)

NOTE IMPORTANTI PER CHI MANUTIENE QUESTO SCRIPT:
  - Il sito ha una protezione anti-bot che ha continuato a restituire 403
    anche con header completi da browser, sessione persistente, Referer e
    ritentativi (confermato da due esecuzioni reali della Action, log del
    2026-09-19 e del 2026-10-03). Questo esclude un blocco basato sui soli
    header HTTP: per questo lo script ora usa Playwright (Chromium
    headless) per caricare le pagine come farebbe un browser vero,
    eseguendo anche eventuale JavaScript di verifica (vedi `fetch`,
    `_get_browser_context`). Se il 403 dovesse persistere ANCHE con
    Playwright, il blocco e' molto probabilmente legato alla rete/IP dei
    runner di GitHub Actions (intervalli IP noti di provider cloud spesso
    bloccati a prescindere dal browser usato): in quel caso l'unica strada
    sarebbe eseguire lo scraping da una rete non riconoscibile come
    "datacenter" (es. un servizio di proxy residenziali), il che esula
    dallo scopo di un progetto gratuito/amatoriale come questo.
  - Le classi CSS esatte del sito non sono state verificate manualmente in
    fase di sviluppo iniziale. L'estrazione e' quindi basata su pattern
    generici (tag semantici, regex sulle date in italiano) pensati per
    essere ragionevolmente robusti ai cambi di markup. Se l'estrazione di
    titolo/data/descrizione risultasse imprecisa, vedi le funzioni
    `extract_title_from_detail`, `extract_date_from_detail` e
    `extract_description_from_detail`: sono i punti da aggiustare.
  - Se in futuro comparisse un terzo prefisso di dettaglio (oltre a
    "notizie" e "comunicati-stampa"), aggiungilo a `DETAIL_PATH_RE` e a
    `LISTING_URLS`.
"""

import re
import sys
import time
import random
from datetime import datetime
from email.utils import format_datetime
from urllib.parse import urljoin
from xml.sax.saxutils import escape

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Error as PlaywrightError

try:
    from zoneinfo import ZoneInfo
    ROME_TZ = ZoneInfo("Europe/Rome")
except Exception:  # pragma: no cover
    ROME_TZ = None

LISTING_URLS = [
    "https://prefettura.interno.gov.it/it/prefetture/mantova/notizie",
    "https://prefettura.interno.gov.it/it/prefetture/mantova/evidenza/comunicati-stampa",
]
BASE_URL = "https://prefettura.interno.gov.it"
CHANNEL_LINK = LISTING_URLS[0]
# URL pubblico del feed generato (GitHub Pages pubblica dalla root del
# branch main, non dalla cartella /docs come sorgente: per questo il path
# include "docs/").
FEED_PUBLIC_URL = "https://mbmichele.github.io/feed_prefettura_mn/docs/feed.xml"

# Path dei prefissi sotto cui possono trovarsi le pagine di dettaglio di un
# comunicato. Lo stesso comunicato puo' avere lo stesso slug sotto prefissi
# diversi (alias Drupal): la deduplica avviene sullo slug, non sull'URL.
DETAIL_PATH_RE = re.compile(r"/(?:notizie|comunicati-stampa)/([^/?#]+?)/?$")
FEED_PATH = "docs/feed.xml"
MAX_ITEMS = 60
REQUEST_TIMEOUT = 25
REQUEST_DELAY_MIN = 1.5  # cortesia verso il server tra una richiesta e l'altra
REQUEST_DELAY_MAX = 3.0
MAX_RETRIES = 3

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"

# Stato globale di Playwright: un solo browser/contesto per tutta
# l'esecuzione dello script, cosi' i cookie restano condivisi tra le
# richieste (come in una normale sessione di navigazione).
_playwright = None
_browser = None
_browser_context = None
_warmed_up = False


def _get_context():
    """Avvia Playwright/Chromium al primo utilizzo e riusa lo stesso
    browser context per tutte le richieste successive."""
    global _playwright, _browser, _browser_context
    if _browser_context is not None:
        return _browser_context

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=True)
    _browser_context = _browser.new_context(
        user_agent=USER_AGENT,
        locale="it-IT",
        viewport={"width": 1366, "height": 768},
        extra_http_headers={"Accept-Language": ACCEPT_LANGUAGE},
    )
    return _browser_context


def close_browser():
    """Chiude ordinatamente Chromium/Playwright a fine esecuzione."""
    global _playwright, _browser, _browser_context
    try:
        if _browser is not None:
            _browser.close()
    except Exception:
        pass
    try:
        if _playwright is not None:
            _playwright.stop()
    except Exception:
        pass
    _browser = None
    _browser_context = None
    _playwright = None


def _warm_up():
    """Visita la home del sito con un browser vero prima delle pagine di
    elenco, per far assegnare al contesto eventuali cookie richiesti dal
    WAF/anti-bot."""
    global _warmed_up
    if _warmed_up:
        return
    context = _get_context()
    page = context.new_page()
    try:
        page.goto(BASE_URL, timeout=REQUEST_TIMEOUT * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
    except PlaywrightError as exc:
        print(f"[AVVISO] Warm-up su {BASE_URL} fallito: {exc}", file=sys.stderr)
    finally:
        page.close()
    _warmed_up = True
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


MESI_ITA = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(MESI_ITA.keys()) + r")\s+(\d{4})",
    re.IGNORECASE,
)

# Frammenti di testo boilerplate da scartare quando si cerca la descrizione
BOILERPLATE_SNIPPETS = [
    "vai al contenuto principale",
    "ultimo aggiornamento",
    "minuti di lettura",
    "minuto di lettura",
    "leggi tutto",
    "condividi",
    "prefettura - ufficio territoriale del governo",
    "torna su",
]


def _looks_like_bot_challenge(html: str) -> bool:
    lowered = html.lower()
    signals = [
        "just a moment",
        "attention required",
        "cf-browser-verification",
        "captcha",
        "access denied",
    ]
    return any(s in lowered for s in signals)


def fetch(url: str, referer: str | None = None) -> BeautifulSoup | None:
    """Carica una pagina con un browser headless reale (Playwright/
    Chromium) invece di una semplice richiesta HTTP: il sito ha continuato
    a rispondere 403 anche con header completi e sessione persistente, il
    che indica una verifica piu' sofisticata di un controllo sugli header."""
    _warm_up()
    context = _get_context()

    status = None
    html = None
    for attempt in range(1, MAX_RETRIES + 1):
        page = context.new_page()
        try:
            try:
                response = page.goto(
                    url,
                    referer=referer,
                    timeout=REQUEST_TIMEOUT * 1000,
                    wait_until="domcontentloaded",
                )
            except PlaywrightError as exc:
                print(f"[ERRORE] Navigazione fallita per {url} (tentativo {attempt}): {exc}", file=sys.stderr)
                status = None
            else:
                status = response.status if response else None
                if status == 200:
                    # piccola attesa per eventuale contenuto/verifica caricati via JS
                    page.wait_for_timeout(1200)
                    html = page.content()
        finally:
            page.close()

        if status == 200 and html is not None:
            break

        if status in (403, 429, 503) or status is None:
            wait = (attempt * 3) + random.uniform(1, 3)
            print(
                f"[AVVISO] Status {status} per {url} "
                f"(tentativo {attempt}/{MAX_RETRIES}), riprovo tra {wait:.1f}s.",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        else:
            print(f"[ERRORE] Status {status} per {url}", file=sys.stderr)
            return None

    if html is None:
        print(f"[ERRORE] Impossibile ottenere {url} dopo {MAX_RETRIES} tentativi (ultimo status: {status}).", file=sys.stderr)
        return None

    if _looks_like_bot_challenge(html):
        print(
            f"[ERRORE] La risposta per {url} sembra una pagina di verifica "
            "anti-bot, non il contenuto reale.",
            file=sys.stderr,
        )
        return None

    return BeautifulSoup(html, "html.parser")


def strip_leading_category_labels(text: str) -> str:
    """
    Rimuove automaticamente eventuali etichette di categoria iniziali che
    terminano con una virgola (es. "Cronaca, Sicurezza, Il testo vero e
    proprio...") indipendentemente da quante siano.
    """
    if not text:
        return text
    pattern = re.compile(r"^\s*(?:[^,\.]{1,60},\s*)+")
    cleaned = pattern.sub("", text)
    return cleaned.strip()


def extract_slug(url: str):
    match = DETAIL_PATH_RE.search(url)
    return match.group(1) if match else None


def find_detail_links(listing_soup: BeautifulSoup) -> list[str]:
    """Trova i link di dettaglio in una pagina di elenco (notizie o
    comunicati-stampa), escludendo le pagine di elenco stesse."""
    listing_urls_normalized = {u.rstrip("/") for u in LISTING_URLS}
    links = []
    seen = set()
    for a in listing_soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(BASE_URL, href)
        if full.rstrip("/") in listing_urls_normalized:
            continue
        if extract_slug(full) and full not in seen:
            seen.add(full)
            links.append(full)
    return links


def extract_title_from_detail(soup: BeautifulSoup, fallback: str) -> str:
    for tag_name in ("h1", "h2"):
        tag = soup.find(tag_name)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)
    return fallback


def extract_date_from_detail(soup: BeautifulSoup):
    text = soup.get_text(" ", strip=True)
    match = DATE_RE.search(text)
    if not match:
        return None
    day = int(match.group(1))
    month = MESI_ITA[match.group(2).lower()]
    year = int(match.group(3))
    try:
        dt = datetime(year, month, day)
        if ROME_TZ:
            dt = dt.replace(tzinfo=ROME_TZ)
        return dt
    except ValueError:
        return None


def extract_description_from_detail(soup: BeautifulSoup) -> str:
    container = soup.find("article") or soup.find("main") or soup

    paragraphs = []
    for p in container.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if not txt or len(txt) < 25:
            continue
        low = txt.lower()
        if any(b in low for b in BOILERPLATE_SNIPPETS):
            continue
        paragraphs.append(txt)
        if sum(len(x) for x in paragraphs) > 500:
            break

    description = " ".join(paragraphs)
    description = strip_leading_category_labels(description)
    if len(description) > 600:
        description = description[:597].rstrip() + "..."
    return description


def scrape_new_item(url: str, link_text_fallback: str, referer: str | None = None):
    soup = fetch(url, referer=referer)
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))  # cortesia prima della prossima richiesta
    if soup is None:
        return None

    title = extract_title_from_detail(soup, fallback=link_text_fallback or url)
    title = strip_leading_category_labels(title)
    pub_date = extract_date_from_detail(soup)
    description = extract_description_from_detail(soup)

    if not description:
        # fallback minimo per non pubblicare un item completamente vuoto
        description = title

    return {
        "title": title,
        "link": url,
        "guid": url,
        "pub_date": pub_date,
        "description": description,
    }


def load_existing_items(path: str) -> dict:
    """Rilegge docs/feed.xml esistente (se presente) per non ri-scaricare
    le pagine di dettaglio di comunicati gia' noti e per preservare la
    cronologia dei comunicati non piu' in prima pagina."""
    import os

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    soup = BeautifulSoup(content, "xml")
    items = {}
    for item in soup.find_all("item"):
        guid_tag = item.find("guid")
        if not guid_tag or not guid_tag.text:
            continue
        guid = guid_tag.text.strip()
        title = item.find("title").text if item.find("title") else ""
        link = item.find("link").text if item.find("link") else guid
        description = item.find("description").text if item.find("description") else ""
        pub_date_text = item.find("pubDate").text if item.find("pubDate") else None
        pub_date = None
        if pub_date_text:
            try:
                from email.utils import parsedate_to_datetime
                pub_date = parsedate_to_datetime(pub_date_text)
            except (TypeError, ValueError):
                pub_date = None
        items[guid] = {
            "title": title,
            "link": link,
            "guid": guid,
            "pub_date": pub_date,
            "description": description,
        }
    return items


def build_rss(items: list) -> str:
    now = datetime.now(ROME_TZ) if ROME_TZ else datetime.utcnow()

    items_xml = []
    for it in items:
        pub_date = it.get("pub_date")
        pub_date_str = format_datetime(pub_date) if pub_date else format_datetime(now)
        items_xml.append(
            "    <item>\n"
            f"      <title>{escape(it['title'])}</title>\n"
            f"      <link>{escape(it['link'])}</link>\n"
            f"      <guid isPermaLink=\"true\">{escape(it['guid'])}</guid>\n"
            f"      <pubDate>{pub_date_str}</pubDate>\n"
            f"      <description>{escape(it['description'])}</description>\n"
            "    </item>"
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Prefettura di Mantova - Notizie e comunicati stampa (feed non ufficiale)</title>
    <link>{escape(CHANNEL_LINK)}</link>
    <description>Feed RSS non ufficiale, generato automaticamente, delle notizie e dei comunicati stampa pubblicati sul sito della Prefettura di Mantova. Non è un servizio ufficiale della Prefettura.</description>
    <language>it-IT</language>
    <atom:link href="{escape(FEED_PUBLIC_URL)}" rel="self" type="application/rss+xml" />
    <lastBuildDate>{format_datetime(now)}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    return rss


def _main():
    # slug -> (url, testo del link, in quale pagina di elenco e' comparso)
    candidates_by_slug = {}
    any_listing_ok = False
    detail_referer = {}  # url dettaglio -> pagina di elenco da usare come Referer

    for listing_url in LISTING_URLS:
        listing_soup = fetch(listing_url, referer=BASE_URL)
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
        if listing_soup is None:
            print(f"[AVVISO] Impossibile leggere la pagina di elenco: {listing_url}", file=sys.stderr)
            continue
        any_listing_ok = True

        detail_links = find_detail_links(listing_soup)
        print(f"{listing_url}: trovati {len(detail_links)} link di dettaglio.")

        link_text_map = {}
        for a in listing_soup.find_all("a", href=True):
            full = urljoin(BASE_URL, a["href"])
            txt = a.get_text(strip=True)
            if full in detail_links and txt and full not in link_text_map:
                link_text_map[full] = txt

        for url in detail_links:
            slug = extract_slug(url)
            if slug is None:
                continue
            detail_referer.setdefault(url, listing_url)
            if slug not in candidates_by_slug:
                candidates_by_slug[slug] = (url, link_text_map.get(url, ""))

    if not any_listing_ok:
        print("[ERRORE] Nessuna delle pagine di elenco e' stata letta con successo.", file=sys.stderr)
        sys.exit(1)

    if not candidates_by_slug:
        print(
            "[ERRORE] Nessun link di dettaglio trovato in nessuna pagina di elenco. "
            "La struttura del sito potrebbe essere cambiata: controllare "
            "find_detail_links() e DETAIL_PATH_RE in questo script.",
            file=sys.stderr,
        )
        sys.exit(1)

    existing = load_existing_items(FEED_PATH)
    # normalizza gli item esistenti per slug, cosi' un comunicato gia' noto
    # non viene ri-scaricato anche se ricompare sotto l'altro prefisso URL
    existing_by_slug = {}
    for guid, item in existing.items():
        slug = extract_slug(guid) or guid
        existing_by_slug[slug] = item

    merged_by_slug = dict(existing_by_slug)
    new_count = 0
    for slug, (url, link_text) in candidates_by_slug.items():
        if slug in merged_by_slug:
            continue
        item = scrape_new_item(url, link_text_fallback=link_text, referer=detail_referer.get(url))
        if item:
            merged_by_slug[slug] = item
            new_count += 1

    print(f"Nuovi comunicati scaricati in questa esecuzione: {new_count}")

    items = list(merged_by_slug.values())
    items.sort(key=lambda it: it["pub_date"] or datetime.min.replace(tzinfo=ROME_TZ) if ROME_TZ else datetime.min, reverse=True)
    items = items[:MAX_ITEMS]

    rss_xml = build_rss(items)

    import os
    os.makedirs("docs", exist_ok=True)
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(rss_xml)

    print(f"Feed scritto in {FEED_PATH} con {len(items)} elementi totali.")


def main():
    try:
        _main()
    finally:
        close_browser()


if __name__ == "__main__":
    main()
