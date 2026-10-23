"""LLM yokken (anahtar yok ya da kota dolu) kural tabanlı niyet çıkarma.

Kalite LLM'den düşüktür ama hat her şehir için uçtan uca çalışmaya devam eder.
"""

from __future__ import annotations

import re

from app.models import Intent, IntentParse

PROVINCES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
    "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa",
    "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum",
    "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir",
    "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kilis", "Kırıkkale", "Kırklareli",
    "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak",
    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak",
]  # fmt: skip

REGIONS = [
    "Kapadokya", "Göreme", "Ürgüp", "Uçhisar", "Avanos", "Bodrum", "Fethiye", "Kaş", "Kalkan", "Alanya", "Side",
    "Kemer", "Marmaris", "Datça", "Çeşme", "Alaçatı", "Ayvalık", "Assos", "Efes", "Selçuk", "Şirince", "Pamukkale",
    "Safranbolu", "Amasra", "Midyat", "Hasankeyf", "Halfeti", "Göbeklitepe", "Bozcaada", "Gökçeada", "Uzungöl",
    "Kadıköy", "Beyoğlu", "Üsküdar", "Beşiktaş", "Sultanahmet", "Balat", "Cumalıkızık",
    "Paris", "Roma", "Londra", "Barselona", "Amsterdam", "Berlin", "Prag", "Viyana", "Budapeşte", "Atina", "Lizbon",
]  # fmt: skip

INTEREST_WORDS: dict[str, tuple[str, ...]] = {
    "tarih": ("tarih", "antik", "kale", "saray", "ören", "harabe", "osmanlı", "bizans"),
    "muze": ("müze",),
    "dini": ("cami", "kilise", "dini", "manastır", "türbe", "sinagog"),
    "mimari": ("mimari", "mimar", "yapı"),
    "park": ("park", "bahçe"),
    "doga": ("doğa", "vadi", "orman", "göl", "şelale", "yürüyüş parkuru"),
    "manzara": ("manzara", "gün batımı", "seyir", "teras", "deniz", "sahil", "kordon"),
    "yemek": ("yemek", "lezzet", "restoran", "gastronomi", "kebap", "yöresel"),
    "kahve": ("kahve", "kafe", "cafe", "tatlı"),
    "sanat": ("sanat", "galeri", "sergi", "tiyatro"),
    "alisveris": ("alışveriş", "çarşı", "pazar", "bedesten"),
}

EDIT_WORDS = ("çıkar", "kaldır", "olmasın", "istemiyorum", "atla", "sil", "değiştir", "başka", "yerine", "ekle")
_CAR = re.compile(r"(araç|araba|otomobil|sürüş|kiralık)")
_WALK = re.compile(r"(yürü|yaya)")
_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


def tr_lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def tr_title(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    first = {"i": "İ", "ı": "I"}.get(text[0], text[0].upper())
    return first + text[1:]


_PLACES = sorted(PROVINCES + REGIONS, key=len, reverse=True)


def find_city(text: str) -> str | None:
    low = tr_lower(text)
    for name in _PLACES:
        if re.search(rf"(?<!\w){re.escape(tr_lower(name))}", low):
            return name
    return None


def guess_city_from_short_message(message: str) -> str | None:
    """'Ankara', 'Safranbolu'da' gibi kısa mesajlarda yer adını ekleri atarak tahmin eder (Nominatim doğrular)."""
    words = message.strip().split()
    if not 1 <= len(words) <= 3:
        return None
    candidate = re.split(r"['’]", " ".join(words))[0].strip(" .,!?")
    return tr_title(candidate) if len(candidate) >= 3 else None


def rule_parse(message: str, previous: Intent | None = None) -> IntentParse:
    low = tr_lower(message)
    city = find_city(message)
    editing = previous is not None and (city is None or tr_lower(city) == tr_lower(previous.sehir))
    if city is None and not editing:
        city = guess_city_from_short_message(message)

    ilgi = [key for key, words in INTEREST_WORDS.items() if any(w in low for w in words)]
    if not ilgi:
        ilgi = list(previous.ilgi) if editing and previous else ["tarih", "muze"]

    if "yarım gün" in low or "yarim gun" in low or "birkaç saat" in low:
        sure = "yarim_gun"
    elif re.search(r"(2|iki)\s*gün|hafta ?sonu", low):
        sure = "2_gun"
    else:
        sure = previous.sure if editing and previous else "1_gun"

    if _CAR.search(low):
        mod = "arac"
    elif _WALK.search(low):
        mod = "yuruyus"
    else:
        mod = previous.mod if editing and previous else "yuruyus"

    time_match = _TIME.search(low)
    start = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else None
    wishes = ["gün batımı"] if "gün batımı" in low else []

    if editing and previous:
        mentions_mode = bool(_CAR.search(low) or _WALK.search(low))
        mode_only = mentions_mode and not any(w in low for w in EDIT_WORDS + ("yemek", "öğle"))
        return IntentParse(
            sehir=previous.sehir,
            ilce=previous.ilce,
            ilgi=ilgi,
            sure=sure,
            mod=mod,
            baslangic_saati=start or previous.baslangic_saati,
            ozel_istekler=wishes or list(previous.ozel_istekler),
            tur="duzenle",
            yalnizca_mod=mode_only,
        )

    if not city:
        return IntentParse(sehir=None, soru="Hangi şehir için rota kuralım? Örneğin “Ankara'da tarih dolu bir gün”.")
    return IntentParse(
        sehir=city, ilgi=ilgi, sure=sure, mod=mod, baslangic_saati=start, ozel_istekler=wishes, tur="yeni"
    )
