"""Perfil do SpkPvP Client: instância Fabric com o mod SpkPvP e mods de desempenho."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import instances, modrinth, net, paths, settings
from .instances import Instance

RELEASE_URL = "https://github.com/spk768/SpkPvP-Client/releases/latest/download/spkpvp-{mc}.jar"
MOD_FILE = "spkpvp.jar"

# Módulos do mod (mesmos ids de mod/src/.../module). O launcher edita o mesmo
# arquivo de configuração que o jogo lê, então ligar/desligar aqui vale no jogo.
MODULES = [
    {"id": "fps", "name": "FPS", "category": "HUD", "description": "Mostra os quadros por segundo.", "default": True},
    {"id": "cps", "name": "CPS", "category": "HUD", "description": "Cliques por segundo (esquerdo | direito).",
     "default": True},
    {"id": "keystrokes", "name": "Keystrokes", "category": "HUD",
     "description": "Teclas WASD, espaço e cliques na tela.", "default": True},
    {"id": "armor", "name": "Armor Status", "category": "HUD",
     "description": "Armadura e item na mão com durabilidade.", "default": True},
    {"id": "potions", "name": "Efeitos de poção", "category": "HUD",
     "description": "Efeitos ativos com o tempo restante.", "default": True},
    {"id": "coords", "name": "Coordenadas", "category": "HUD", "description": "XYZ e direção.", "default": False},
    {"id": "ping", "name": "Ping", "category": "HUD", "description": "Latência com o servidor.", "default": True},
    {"id": "clock", "name": "Relógio", "category": "HUD", "description": "Hora do sistema.", "default": False},
    {"id": "server", "name": "Servidor", "category": "HUD", "description": "Endereço do servidor atual.",
     "default": False},
    {"id": "togglesprint", "name": "Toggle Sprint", "category": "Mecânica",
     "description": "Correr sempre ligado (tecla V alterna).", "default": True},
    {"id": "zoom", "name": "Zoom", "category": "Mecânica",
     "description": "Segure C para dar zoom; role o mouse para ajustar.", "default": True},
    {"id": "fullbright", "name": "Fullbright", "category": "Visual",
     "description": "Brilho máximo, sem escuridão.", "default": False},
    {"id": "cosmetics", "name": "Cosméticos", "category": "Visual",
     "description": "Mostra capas e asas dos jogadores SpkPvP.", "default": True},
]


def profile_name(mc: str) -> str:
    return f"SpkPvP {mc}"


def get_instance(create: bool = True) -> Instance | None:
    """Instância do client para a versão configurada (criada na primeira vez)."""
    mc = settings.get("minecraft")
    for inst in instances.list_all():
        if inst.pack.get("source") == "spkpvp" and inst.minecraft == mc:
            return inst
    if not create:
        return None
    return instances.create(profile_name(mc), mc, "fabric", pack={"source": "spkpvp", "title": "SpkPvP Client"})


def config_dir(inst: Instance) -> Path:
    path = inst.game_dir / "config" / "spkpvp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _modules_file(inst: Instance) -> Path:
    return config_dir(inst) / "modules.json"


def read_modules(inst: Instance) -> list[dict]:
    try:
        saved = json.loads(_modules_file(inst).read_text("utf-8"))
    except (OSError, ValueError):
        saved = {}
    out = []
    for m in MODULES:
        cur = saved.get(m["id"]) if isinstance(saved.get(m["id"]), dict) else {}
        out.append({**m, "enabled": bool(cur.get("enabled", m["default"]))})
    return out


def set_module(inst: Instance, module_id: str, enabled: bool) -> None:
    if module_id not in {m["id"] for m in MODULES}:
        raise KeyError(module_id)
    path = _modules_file(inst)
    try:
        saved = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        saved = {}
    entry = saved.get(module_id) if isinstance(saved.get(module_id), dict) else {}
    entry["enabled"] = enabled  # mantém posição/escala salvas pelo editor de HUD do jogo
    saved[module_id] = entry
    path.write_text(json.dumps(saved, indent=2), "utf-8")


def write_client_config(inst: Instance) -> None:
    """Configuração lida pelo mod: onde buscar os cosméticos."""
    (config_dir(inst) / "client.json").write_text(
        json.dumps({"api_url": settings.get("store_url").rstrip("/")}, indent=2), "utf-8")


def install_mod(inst: Instance, log=print) -> None:
    source = settings.get("mod_url") or RELEASE_URL.format(mc=inst.minecraft)
    dest = inst.mods_dir / MOD_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(source).is_file():
        shutil.copyfile(source, dest)
        return
    tmp = paths.cache_dir() / f"spkpvp-{inst.minecraft}.jar"
    try:
        tmp.unlink(missing_ok=True)
        net.download(net.Download(source, tmp))
        shutil.move(str(tmp), dest)
        log("Mod SpkPvP atualizado")
    except Exception as e:  # noqa: BLE001 - sem internet ainda dá para jogar com o jar atual
        if not dest.exists():
            raise RuntimeError(f"Não foi possível baixar o mod SpkPvP ({source}): {e}") from None
        log(f"Aviso: não foi possível atualizar o mod SpkPvP ({e}); usando a versão instalada")


def prepare(inst: Instance, log=print) -> None:
    """Instala/atualiza o mod SpkPvP e os mods de desempenho antes de jogar."""
    for project in settings.get("performance_mods") or []:
        try:
            modrinth.add_project(inst, project, log)
        except Exception as e:  # noqa: BLE001 - mod opcional
            log(f"Aviso: {project} não instalado: {e}")
    install_mod(inst, log)
    write_client_config(inst)
