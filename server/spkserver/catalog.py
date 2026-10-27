"""Catálogo de cosméticos. Preços em centavos (BRL).

O catálogo fica no código para que preço e existência de um item nunca venham
do cliente; o banco guarda apenas o que cada jogador comprou e equipou.
"""
from __future__ import annotations

SLOTS = ("cape", "wings")

COSMETICS: dict[str, dict] = {}


def _add(cid: str, type_: str, name: str, price: int, rarity: str, description: str,
         featured: bool = False) -> None:
    COSMETICS[cid] = {"id": cid, "type": type_, "name": name, "price": price, "rarity": rarity,
                      "description": description, "featured": featured,
                      "texture": f"/textures/{cid}.png"}


_add("cape_spk", "cape", "Capa SpkPvP", 0, "comum", "A capa oficial do client. Grátis para todos.")
_add("cape_ember", "cape", "Capa Brasa", 990, "rara", "Gradiente de fogo para quem vive no combo.", True)
_add("cape_ocean", "cape", "Capa Oceano", 990, "rara", "Azul profundo com ondas.")
_add("cape_toxic", "cape", "Capa Tóxica", 1490, "épica", "Verde neon com listras.")
_add("cape_royal", "cape", "Capa Real", 1990, "lendária", "Roxo e dourado, para os campeões.", True)
_add("cape_brasil", "cape", "Capa Brasil", 1490, "épica", "Verde, amarelo e azul.")
_add("wings_angel", "wings", "Asas de Anjo", 2490, "épica", "Asas brancas que batem enquanto você anda.", True)
_add("wings_demon", "wings", "Asas Demoníacas", 2990, "lendária", "Asas vermelho-escuras.")
_add("wings_dragon", "wings", "Asas de Dragão", 3490, "lendária", "Asas roxas de dragão.")

BUNDLES: dict[str, dict] = {
    "bundle_starter": {"id": "bundle_starter", "type": "bundle", "name": "Pacote Iniciante",
                       "items": ["cape_ember", "cape_ocean", "wings_angel"], "price": 3490, "rarity": "pacote",
                       "description": "Duas capas + Asas de Anjo com desconto.", "featured": True,
                       "texture": "/textures/cape_ember.png"},
}


def get(item_id: str) -> dict:
    """Retorna um cosmético ou pacote. KeyError se não existir."""
    if item_id in COSMETICS:
        return COSMETICS[item_id]
    return BUNDLES[item_id]


def expand(item_id: str) -> list[str]:
    """Ids dos cosméticos concedidos por um item (pacote = vários)."""
    item = get(item_id)
    return list(item["items"]) if item["type"] == "bundle" else [item_id]


def all_items() -> list[dict]:
    return list(COSMETICS.values()) + list(BUNDLES.values())
