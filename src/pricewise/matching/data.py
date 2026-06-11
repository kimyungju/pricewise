"""Synthetic product-pair dataset for the same-product matching head.

Retailer listings name the same product in wildly different surface forms
("Apple AirPods Pro (2nd Generation)" vs "NEW AirPods Pro 2 USB-C | Free
Shipping"), while *near* products differ by one token ("iPhone 15" vs
"iPhone 15 Pro"). There is no labelled data for this, so we generate pairs
from a seed catalog:

  positives       — two different renderings of the same product
  hard negatives  — two products from the same family (the failure mode
                    that actually hurts price comparison)
  easy negatives  — two unrelated products

Splits are made at the FAMILY level so no product (or its siblings) leaks
from train into val/test.
"""

from __future__ import annotations

import random

# Each product: stable id, brand, canonical name, aliases (how retailers
# actually write it), family (groups near-identical variants), category.
_P = [
    # Apple phones
    ("iphone15", "Apple", "iPhone 15", ["iPhone 15", "iPhone 15 128GB", "Apple iPhone15"], "iPhone 15", "phone"),
    ("iphone15plus", "Apple", "iPhone 15 Plus", ["iPhone 15 Plus", "iPhone 15+"], "iPhone 15", "phone"),
    ("iphone15pro", "Apple", "iPhone 15 Pro", ["iPhone 15 Pro", "iPhone 15Pro Titanium"], "iPhone 15", "phone"),
    ("iphone15promax", "Apple", "iPhone 15 Pro Max", ["iPhone 15 Pro Max", "iPhone 15 ProMax"], "iPhone 15", "phone"),
    ("iphone16", "Apple", "iPhone 16", ["iPhone 16", "Apple iPhone 16 (2024)"], "iPhone 16", "phone"),
    ("iphone16pro", "Apple", "iPhone 16 Pro", ["iPhone 16 Pro", "iPhone16 Pro"], "iPhone 16", "phone"),
    # Apple audio
    ("airpodspro2", "Apple", "AirPods Pro 2", ["AirPods Pro 2", "AirPods Pro (2nd Generation)", "AirPods Pro 2nd Gen USB-C"], "AirPods", "audio"),
    ("airpods4", "Apple", "AirPods 4", ["AirPods 4", "AirPods (4th Generation)"], "AirPods", "audio"),
    ("airpodsmax", "Apple", "AirPods Max", ["AirPods Max", "AirPods Max Over-Ear"], "AirPods", "audio"),
    # Apple computers / tablets / watch
    ("mbam3", "Apple", "MacBook Air M3 13-inch", ["MacBook Air M3 13\"", "MacBook Air 13 M3 8GB/256GB", "MacBook Air M3"], "MacBook", "laptop"),
    ("mbpm4", "Apple", "MacBook Pro M4 14-inch", ["MacBook Pro M4 14\"", "MacBook Pro 14 M4"], "MacBook", "laptop"),
    ("ipadair11", "Apple", "iPad Air 11-inch M2", ["iPad Air 11 M2", "iPad Air (M2, 11-inch)"], "iPad", "tablet"),
    ("ipadpro11", "Apple", "iPad Pro 11-inch M4", ["iPad Pro 11 M4", "iPad Pro (M4)"], "iPad", "tablet"),
    ("watchs10", "Apple", "Apple Watch Series 10", ["Watch Series 10", "Apple Watch S10 46mm"], "Apple Watch", "wearable"),
    ("watchultra2", "Apple", "Apple Watch Ultra 2", ["Watch Ultra 2", "Apple Watch Ultra2 49mm"], "Apple Watch", "wearable"),
    # Samsung
    ("s24", "Samsung", "Galaxy S24", ["Galaxy S24", "Samsung S24 5G"], "Galaxy S24", "phone"),
    ("s24plus", "Samsung", "Galaxy S24+", ["Galaxy S24+", "Galaxy S24 Plus"], "Galaxy S24", "phone"),
    ("s24ultra", "Samsung", "Galaxy S24 Ultra", ["Galaxy S24 Ultra", "S24 Ultra 512GB"], "Galaxy S24", "phone"),
    ("buds3", "Samsung", "Galaxy Buds3", ["Galaxy Buds3", "Samsung Buds 3"], "Galaxy Buds", "audio"),
    ("buds3pro", "Samsung", "Galaxy Buds3 Pro", ["Galaxy Buds3 Pro", "Buds 3 Pro"], "Galaxy Buds", "audio"),
    ("gwatch7", "Samsung", "Galaxy Watch 7", ["Galaxy Watch7", "Samsung Watch 7 44mm"], "Galaxy Watch", "wearable"),
    ("tabs10", "Samsung", "Galaxy Tab S10", ["Galaxy Tab S10", "Tab S10 11\""], "Galaxy Tab", "tablet"),
    # Sony
    ("xm5", "Sony", "WH-1000XM5", ["WH-1000XM5", "Sony 1000XM5 Wireless Headphones", "WH1000XM5"], "Sony 1000X", "audio"),
    ("xm4", "Sony", "WH-1000XM4", ["WH-1000XM4", "Sony 1000XM4"], "Sony 1000X", "audio"),
    ("wfxm5", "Sony", "WF-1000XM5", ["WF-1000XM5", "Sony WF1000XM5 Earbuds"], "Sony 1000X", "audio"),
    ("ps5", "Sony", "PlayStation 5", ["PlayStation 5", "PS5 Console Disc Edition", "Sony PS5"], "PS5", "console"),
    ("ps5digital", "Sony", "PlayStation 5 Digital Edition", ["PS5 Digital Edition", "PlayStation 5 Digital"], "PS5", "console"),
    ("ps5pro", "Sony", "PlayStation 5 Pro", ["PS5 Pro", "PlayStation 5 Pro 2TB"], "PS5", "console"),
    # Bose
    ("qcultra", "Bose", "QuietComfort Ultra", ["QuietComfort Ultra Headphones", "Bose QC Ultra"], "Bose QC", "audio"),
    ("qc45", "Bose", "QuietComfort 45", ["QuietComfort 45", "Bose QC45"], "Bose QC", "audio"),
    ("slflex", "Bose", "SoundLink Flex", ["SoundLink Flex Bluetooth Speaker", "Bose SoundLink Flex"], "SoundLink", "audio"),
    # Nintendo
    ("switch2", "Nintendo", "Switch 2", ["Nintendo Switch 2", "Switch 2 Console"], "Switch", "console"),
    ("switcholed", "Nintendo", "Switch OLED", ["Switch OLED Model", "Nintendo Switch OLED White"], "Switch", "console"),
    # PCs and laptops
    ("xps13", "Dell", "XPS 13", ["Dell XPS 13 9345", "XPS 13 Laptop"], "Dell XPS", "laptop"),
    ("xps15", "Dell", "XPS 15", ["Dell XPS 15", "XPS 15 OLED"], "Dell XPS", "laptop"),
    ("x1carbon", "Lenovo", "ThinkPad X1 Carbon Gen 12", ["ThinkPad X1 Carbon", "Lenovo X1 Carbon G12"], "ThinkPad", "laptop"),
    ("spectre", "HP", "Spectre x360 14", ["Spectre x360", "HP Spectre x360 2-in-1"], "Spectre", "laptop"),
    ("rogally", "Asus", "ROG Ally X", ["ROG Ally X", "Asus ROG AllyX Handheld"], "ROG Ally", "console"),
    ("steamdeck", "Valve", "Steam Deck OLED", ["Steam Deck OLED 1TB", "SteamDeck OLED"], "Steam Deck", "console"),
    # TV / home
    ("lgc455", "LG", "C4 OLED 55-inch", ["LG C4 55\" OLED TV", "OLED55C4"], "LG C4", "tv"),
    ("lgc465", "LG", "C4 OLED 65-inch", ["LG C4 65\" OLED TV", "OLED65C4"], "LG C4", "tv"),
    ("dysonv15", "Dyson", "V15 Detect", ["Dyson V15 Detect Absolute", "V15 Detect Cordless Vacuum"], "Dyson V", "home"),
    ("dysonv12", "Dyson", "V12 Detect Slim", ["Dyson V12 Slim", "V12 Detect"], "Dyson V", "home"),
    # E-readers / cameras / drones
    ("paperwhite", "Amazon", "Kindle Paperwhite", ["Kindle Paperwhite 16GB", "Paperwhite (11th Gen)"], "Kindle", "ereader"),
    ("kindleoasis", "Amazon", "Kindle Oasis", ["Kindle Oasis 32GB", "Oasis E-reader"], "Kindle", "ereader"),
    ("hero13", "GoPro", "HERO13 Black", ["GoPro HERO 13 Black", "Hero13"], "GoPro", "camera"),
    ("djimini4", "DJI", "Mini 4 Pro", ["DJI Mini 4 Pro Drone", "Mini4 Pro Fly More"], "DJI Mini", "camera"),
    ("a7iv", "Sony", "Alpha 7 IV", ["Sony A7 IV Body", "Alpha7 IV Mirrorless"], "Sony Alpha", "camera"),
    # Accessories
    ("mxmaster3s", "Logitech", "MX Master 3S", ["MX Master 3S Mouse", "Logitech MX Master3S"], "MX", "accessory"),
    ("mxkeys", "Logitech", "MX Keys S", ["MX Keys S Keyboard", "Logitech MXKeys"], "MX", "accessory"),
    ("k2", "Keychron", "K2 V2", ["Keychron K2 Mechanical Keyboard", "K2 Version 2"], "Keychron", "accessory"),
    ("deathadder", "Razer", "DeathAdder V3", ["DeathAdder V3 Gaming Mouse", "Razer Death Adder V3"], "Razer", "accessory"),
    ("anker737", "Anker", "737 Power Bank", ["Anker 737 PowerCore 24K", "737 PowerBank 140W"], "Anker", "accessory"),
    # Speakers / wearables
    ("flip6", "JBL", "Flip 6", ["JBL Flip6 Portable Speaker", "Flip 6 Bluetooth"], "JBL", "audio"),
    ("charge5", "JBL", "Charge 5", ["JBL Charge5", "Charge 5 Speaker"], "JBL", "audio"),
    ("fr265", "Garmin", "Forerunner 265", ["Garmin Forerunner265", "FR 265 GPS Watch"], "Forerunner", "wearable"),
    ("fr965", "Garmin", "Forerunner 965", ["Garmin Forerunner 965", "FR965"], "Forerunner", "wearable"),
    ("charge6", "Fitbit", "Charge 6", ["Fitbit Charge6 Tracker", "Charge 6 Fitness Band"], "Fitbit", "wearable"),
    # Google / Meta / GPU
    ("pixel9", "Google", "Pixel 9", ["Google Pixel 9 128GB", "Pixel9"], "Pixel 9", "phone"),
    ("pixel9pro", "Google", "Pixel 9 Pro", ["Pixel 9 Pro", "Google Pixel9 Pro"], "Pixel 9", "phone"),
    ("budspro2", "Google", "Pixel Buds Pro 2", ["Pixel Buds Pro2", "Google Buds Pro 2"], "Pixel Buds", "audio"),
    ("quest3", "Meta", "Quest 3", ["Meta Quest 3 512GB", "Oculus Quest3"], "Quest", "vr"),
    ("quest3s", "Meta", "Quest 3S", ["Meta Quest 3S", "Quest 3 S 128GB"], "Quest", "vr"),
    ("rtx5070", "Nvidia", "GeForce RTX 5070", ["RTX 5070 12GB", "NVIDIA RTX5070 GPU"], "RTX 50", "gpu"),
    ("rtx5080", "Nvidia", "GeForce RTX 5080", ["RTX 5080 16GB", "NVIDIA RTX5080"], "RTX 50", "gpu"),
]

CATALOG: list[dict] = [
    {"id": pid, "brand": brand, "name": name, "aliases": aliases,
     "family": family, "category": category}
    for pid, brand, name, aliases, family, category in _P
]

_PREFIXES = ["", "", "", "NEW ", "2026 ", "Official ", "Genuine "]
_SUFFIXES = ["", "", " - Free Shipping", " | In Stock", " (Latest Model)",
             " - Fast Delivery", " | Authorized Dealer", ", Sealed"]
_RETAILERS = ["", "", " at Amazon", " - Best Buy", " | Walmart.com",
              " - Target", " | Shopee", " at Lazada"]


def render_title(product: dict, rng: random.Random) -> str:
    """One retailer-style surface form of a product listing title."""
    alias = rng.choice(product["aliases"])
    if rng.random() < 0.5 and not alias.lower().startswith(product["brand"].lower()):
        alias = f"{product['brand']} {alias}"
    title = f"{rng.choice(_PREFIXES)}{alias}{rng.choice(_SUFFIXES)}{rng.choice(_RETAILERS)}"
    if rng.random() < 0.1:
        title = title.upper()
    return title.strip()


def _hard_negative_pool(catalog: list[dict]) -> list[tuple[dict, dict]]:
    by_family: dict[str, list[dict]] = {}
    for p in catalog:
        by_family.setdefault(p["family"], []).append(p)
    pool = []
    for members in by_family.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pool.append((members[i], members[j]))
    return pool


def generate_pairs(catalog: list[dict], n_pairs: int, seed: int) -> list[dict]:
    """Balanced labelled pairs: ~50% positive, negatives split hard/easy."""
    rng = random.Random(seed)
    hard_pool = _hard_negative_pool(catalog)
    pairs: list[dict] = []

    for i in range(n_pairs):
        if i % 2 == 0:  # positive
            p = rng.choice(catalog)
            text_a = render_title(p, rng)
            for _ in range(5):
                text_b = render_title(p, rng)
                if text_b != text_a:
                    break
            pairs.append({
                "text_a": text_a, "text_b": text_b, "label": 1,
                "product_a": p["id"], "product_b": p["id"], "kind": "positive",
            })
        elif i % 4 == 1 and hard_pool:  # hard negative: same family
            a, b = rng.choice(hard_pool)
            pairs.append({
                "text_a": render_title(a, rng), "text_b": render_title(b, rng),
                "label": 0, "product_a": a["id"], "product_b": b["id"],
                "kind": "hard_negative",
            })
        else:  # easy negative: any two distinct products
            a, b = rng.sample(catalog, 2)
            pairs.append({
                "text_a": render_title(a, rng), "text_b": render_title(b, rng),
                "label": 0, "product_a": a["id"], "product_b": b["id"],
                "kind": "easy_negative",
            })
    return pairs


def split_catalog(
    catalog: list[dict],
    seed: int,
    ratios: tuple[float, float] = (0.7, 0.15),
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split at FAMILY level so sibling variants never straddle splits.

    A model that saw "iPhone 15 Pro" in training must not be evaluated on
    "iPhone 15" pairs — family-level splitting prevents that leakage.
    """
    rng = random.Random(seed)
    by_family: dict[str, list[dict]] = {}
    for p in catalog:
        by_family.setdefault(p["family"], []).append(p)

    families = sorted(by_family)
    rng.shuffle(families)

    total = len(catalog)
    train, val, test = [], [], []
    for fam in families:
        if len(train) < ratios[0] * total:
            train.extend(by_family[fam])
        elif len(val) < ratios[1] * total:
            val.extend(by_family[fam])
        else:
            test.extend(by_family[fam])
    return train, val, test
