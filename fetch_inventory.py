"""
CS2 Inventory Tracker - Fetch Script
-------------------------------------
Tento skript se spouští automaticky každý den přes GitHub Actions.
Co dělá:
1. Stáhne tvůj CS2 inventář ze Steamu (veřejné API, bez klíče)
2. Ke každé zbrani stáhne aktuální tržní cenu ze Steam Market
3. Výsledky uloží do data/history.json jako nový denní záznam
4. Přečte data/purchase_prices.json kde máš zapsané nákupní ceny

POZOR: Steam Market API má rate limiting (omezení rychlosti).
Skript proto čeká 3 sekundy mezi každým dotazem na cenu.
"""

import json
import time
import os
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ============================================================
# NASTAVENÍ - TADY ZMĚN STEAM ID NA SVOJE
# ============================================================
STEAM_ID = "76561198356510009"   # Tvoje Steam ID (číslo z URL tvého profilu)
APP_ID = 730                      # 730 = CS2/CS:GO
CONTEXT_ID = 2                    # Vždy 2 pro herní předměty
CURRENCY = 3                      # 3 = EUR (eura). Jiné možnosti: 1=USD, 2=GBP, 6=PLN
DELAY_BETWEEN_REQUESTS = 3.5      # Čekání v sekundách mezi dotazy (kvůli rate limitu)
# ============================================================


def fetch_url(url, max_retries=6):
    """
    Stáhne obsah dané URL. Zkusí to max_retries-krát při chybě.
    Vrací text nebo None při neúspěchu.

    DŮLEŽITÁ POZNÁMKA k chybě "429 Too Many Requests":
    GitHub Actions běží na sdílených serverech, ze kterých posílají
    požadavky na Steam TISÍCE dalších uživatelů najednou (hlavně v
    "kulatých" časech jako 8:00 UTC, kdy mají naplánováno spuštění
    i jiní lidé). Steam proto danou IP adresu na chvíli zablokuje.
    NENÍ to kvůli tvému účtu ani nastavení soukromí!

    Řešení: počkat déle a zkusit to znovu - blokace bývá jen dočasná.
    Proto při chybě 429 čekáme postupně déle (15s, 30s, 60s, 90s...).
    """
    headers = {
        # Říkáme Steamu, že jsme běžný prohlížeč (jinak nás může odmítnout)
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Čekací doby (v sekundách) mezi jednotlivými pokusy - postupně delší
    backoff_delays = [15, 30, 60, 90, 120, 180]

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode("utf-8")

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                print(f"  Pokus {attempt + 1}/{max_retries}: Steam nás dočasně omezil "
                      f"(429 - příliš mnoho požadavků). Čekám {wait}s a zkusím to znovu...")
            else:
                wait = 5
                print(f"  Pokus {attempt + 1}/{max_retries} selhal: HTTP chyba {e.code}")

            if attempt < max_retries - 1:
                time.sleep(wait)

        except Exception as e:
            print(f"  Pokus {attempt + 1}/{max_retries} selhal: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)

    return None


def get_inventory():
    """
    Stáhne tvůj CS2 inventář ze Steam Community API.
    Vrací seznam předmětů (každý má jméno, obrázek atd.)
    """
    print(f"Stahuji inventář pro Steam ID: {STEAM_ID}...")
    
    url = (
        f"https://steamcommunity.com/inventory/{STEAM_ID}/{APP_ID}/{CONTEXT_ID}"
        f"?l=english&count=5000"
    )
    
    raw = fetch_url(url)
    if not raw:
        print("CHYBA: Nepodařilo se stáhnout inventář!")
        print("Ujisti se, že máš inventář nastaven jako VEŘEJNÝ na Steamu.")
        return []
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("CHYBA: Steam vrátil neplatná data (pravděpodobně rate limit nebo privátní inventář)")
        return []
    
    if not data.get("success"):
        print("CHYBA: Steam API vrátilo chybu. Inventář je pravděpodobně privátní.")
        return []
    
    assets = data.get("assets", [])           # seznam "instancí" předmětů (assetid)
    descriptions = data.get("descriptions", [])  # popis každého unikátního předmětu
    
    # Vytvoříme slovník: classid -> popis předmětu
    desc_map = {}
    for desc in descriptions:
        key = f"{desc['classid']}_{desc['instanceid']}"
        desc_map[key] = desc
    
    items = []
    seen_names = {}  # Pro seskupení duplicit (více kusů stejné zbraně)
    
    for asset in assets:
        key = f"{asset['classid']}_{asset['instanceid']}"
        desc = desc_map.get(key, {})
        
        # Přeskočíme předměty, které nelze prodat (non-marketable)
        if not desc.get("marketable", 0):
            continue
        
        name = desc.get("market_hash_name", "")
        if not name:
            continue
        
        # Získáme URL obrázku (Steam CDN)
        icon = desc.get("icon_url", "")
        if icon:
            icon_url = f"https://community.cloudflare.steamstatic.com/economy/image/{icon}/256fx256f"
        else:
            icon_url = ""
        
        # Určíme barvu rarity (vzácnost)
        rarity_color = ""
        for tag in desc.get("tags", []):
            if tag.get("category") == "Rarity":
                rarity_color = tag.get("color", "")
                break
        
        if name in seen_names:
            # Máme více kusů stejného předmětu - zvýšíme počet
            seen_names[name]["quantity"] += 1
        else:
            item_data = {
                "name": name,
                "friendly_name": desc.get("name", name),   # Hezké jméno pro zobrazení
                "icon_url": icon_url,
                "rarity_color": rarity_color,
                "quantity": 1,
                "asset_id": asset.get("assetid", ""),
            }
            seen_names[name] = item_data
            items.append(item_data)
    
    print(f"  Nalezeno {len(items)} unikátních prodejných předmětů.")
    return items


def get_price(market_hash_name):
    """
    Zjistí aktuální tržní cenu předmětu ze Steam Market.
    Vrací číslo (cena v EUR) nebo None.
    
    Příklad URL: https://steamcommunity.com/market/priceoverview/?appid=730&currency=3&market_hash_name=AK-47 | Redline (Field-Tested)
    """
    encoded_name = urllib.parse.quote(market_hash_name)
    url = (
        f"https://steamcommunity.com/market/priceoverview/"
        f"?appid={APP_ID}&currency={CURRENCY}&market_hash_name={encoded_name}"
    )
    
    raw = fetch_url(url)
    if not raw:
        return None
    
    try:
        data = json.loads(raw)
        if not data.get("success"):
            return None
        
        # Steam vrací cenu jako text, např. "12,34€" nebo "$12.34"
        # Musíme ho převést na číslo
        price_str = data.get("median_price") or data.get("lowest_price")
        if not price_str:
            return None
        
        # Odstraníme symboly měn a mezery, normalizujeme desetinnou čárku
        price_clean = price_str.replace("€", "").replace("$", "").replace("£", "")
        price_clean = price_clean.replace(",--", "").replace("\xa0", "").strip()
        
        # Některé ceny mají formát "1.234,56" (tečka jako oddělovač tisíců, čárka jako desetinná)
        if "," in price_clean and "." in price_clean:
            # Formát jako "1.234,56" -> odstraníme tečky, čárku nahradíme tečkou
            price_clean = price_clean.replace(".", "").replace(",", ".")
        elif "," in price_clean:
            # Formát jako "12,34" -> nahradíme čárku tečkou
            price_clean = price_clean.replace(",", ".")
        
        return round(float(price_clean), 2)
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def load_json_file(filepath, default=None):
    """Načte JSON soubor. Pokud neexistuje, vrátí výchozí hodnotu."""
    if default is None:
        default = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json_file(filepath, data):
    """Uloží data do JSON souboru (hezky naformátovaného)."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("CS2 Inventory Tracker - Denní aktualizace")
    print(f"Čas spuštění: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Malé náhodné počkání na startu (5-25 sekund).
    # Důvod: spousta lidí má GitHub Actions naplánované přesně na
    # "kulaté" časy (např. 8:00 UTC). Když všichni vystřelí požadavek
    # na Steam ve stejnou sekundu, zvyšuje se šance na 429 chybu.
    # Náhodné zpoždění nás "rozprostře" a sníží riziko kolize.
    startup_delay = random.randint(5, 25)
    print(f"Čekám {startup_delay}s před startem (rozložení zátěže)...")
    time.sleep(startup_delay)

    # --- Načteme historii a nákupní ceny ---
    history = load_json_file("data/history.json", default={})
    purchase_prices = load_json_file("data/purchase_prices.json", default={})
    
    # --- Stáhneme inventář ---
    items = get_inventory()
    if not items:
        print("\nBez inventáře nelze pokračovat. Ukončuji.")
        return
    
    # --- Stáhneme ceny a vytvoříme dnešní záznam ---
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"\nStahuji ceny pro {len(items)} předmětů (datum: {today})...")
    print("(Čekám 3.5 sekund mezi každým dotazem, abych nepřetížil Steam API)\n")
    
    today_snapshot = {}
    
    for i, item in enumerate(items, 1):
        name = item["name"]
        print(f"  [{i}/{len(items)}] {name[:50]}...", end=" ", flush=True)
        
        price = get_price(name)
        
        if price is not None:
            print(f"→ {price} EUR")
        else:
            print("→ cena nedostupná")
        
        today_snapshot[name] = {
            "price": price,
            "icon_url": item["icon_url"],
            "friendly_name": item["friendly_name"],
            "rarity_color": item["rarity_color"],
            "quantity": item["quantity"],
        }
        
        # Čekáme mezi dotazy (kromě posledního)
        if i < len(items):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # --- Přidáme dnešní záznam do historie ---
    # Struktura history.json:
    # {
    #   "AK-47 | Redline (Field-Tested)": {
    #     "icon_url": "...",
    #     "friendly_name": "...",
    #     "rarity_color": "...",
    #     "prices": {
    #       "2025-01-15": 12.34,
    #       "2025-01-16": 12.50,
    #       ...
    #     }
    #   },
    #   ...
    # }
    
    for name, data in today_snapshot.items():
        if name not in history:
            history[name] = {
                "icon_url": data["icon_url"],
                "friendly_name": data["friendly_name"],
                "rarity_color": data["rarity_color"],
                "prices": {}
            }
        
        # Vždy aktualizujeme metadata (obrázek se může změnit)
        history[name]["icon_url"] = data["icon_url"]
        history[name]["friendly_name"] = data["friendly_name"]
        history[name]["rarity_color"] = data["rarity_color"]
        history[name]["quantity"] = data.get("quantity", 1)
        
        # Přidáme dnešní cenu (None = cena nebyla dostupná)
        if data["price"] is not None:
            history[name]["prices"][today] = data["price"]
    
    # --- Uložíme výsledky ---
    save_json_file("data/history.json", history)
    print(f"\nHistorie uložena do data/history.json")
    
    # --- Vytvoříme souhrn pro web ---
    # Web si načte tento jednoduchý soubor místo složitého history.json
    summary = {}
    for name, data in history.items():
        prices_dict = data.get("prices", {})
        if not prices_dict:
            continue
        
        sorted_dates = sorted(prices_dict.keys())
        latest_price = prices_dict[sorted_dates[-1]] if sorted_dates else None
        first_price = prices_dict[sorted_dates[0]] if sorted_dates else None
        purchase_price = purchase_prices.get(name)
        
        summary[name] = {
            "friendly_name": data.get("friendly_name", name),
            "icon_url": data.get("icon_url", ""),
            "rarity_color": data.get("rarity_color", ""),
            "quantity": data.get("quantity", 1),
            "latest_price": latest_price,
            "first_tracked_price": first_price,
            "purchase_price": purchase_price,
            "price_history": prices_dict,
        }
    
    save_json_file("data/summary.json", summary)
    print(f"Souhrn uložen do data/summary.json")
    
    print("\n✅ Hotovo! Data jsou připravena pro web.")
    print(f"   Celkem sledovaných předmětů: {len(summary)}")
    
    # Spočítáme celkovou hodnotu inventáře
    total_value = sum(
        (v["latest_price"] or 0) * v.get("quantity", 1)
        for v in summary.values()
        if v["latest_price"]
    )
    print(f"   Celková hodnota inventáře: {total_value:.2f} EUR")


if __name__ == "__main__":
    main()
