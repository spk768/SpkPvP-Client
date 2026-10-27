"""Configurações globais do launcher (settings.json)."""
from __future__ import annotations

import json
import os

from . import paths

DEFAULTS = {
    # Client ID de um app Azure com permissão para a API do Minecraft.
    # Necessário apenas para login com conta Microsoft.
    "msa_client_id": "",
    "default_memory_mb": 4096,
    "download_workers": 8,
    # Caminhos de Java por versão principal, ex.: {"17": "/usr/bin/java"}
    "java_paths": {},
    "auto_download_java": True,
    # Versão do Minecraft usada pelo client (a única suportada pelo mod SpkPvP)
    "minecraft": "1.21.1",
    # Servidor da loja de cosméticos (pasta server/ deste repositório)
    "store_url": "http://127.0.0.1:8787",
    # De onde baixar o mod SpkPvP. Vazio = release mais recente no GitHub.
    # Aceita também um caminho local para um .jar (útil ao desenvolver o mod).
    "mod_url": "",
    # Mods de desempenho do Modrinth instalados junto com o client
    "performance_mods": ["fabric-api", "sodium", "lithium"],
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(paths.settings_file().read_text("utf-8")))
    except (OSError, ValueError):
        pass
    if os.environ.get("SPKPVP_MSA_CLIENT_ID"):
        data["msa_client_id"] = os.environ["SPKPVP_MSA_CLIENT_ID"]
    if os.environ.get("SPKPVP_STORE_URL"):
        data["store_url"] = os.environ["SPKPVP_STORE_URL"]
    return data


def save(data: dict) -> None:
    paths.settings_file().write_text(json.dumps(data, indent=2), "utf-8")


def get(key: str):
    return load().get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:  # noqa: A001 - API simples
    data = load()
    data[key] = value
    save(data)
