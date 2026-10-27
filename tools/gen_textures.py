"""Gera as texturas dos cosméticos (capas 64x32 e asas 32x32) em server/spkserver/textures.

Uso: python tools/gen_textures.py
"""
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "server" / "spkserver" / "textures"


def png(path: Path, w: int, h: int, pixel) -> None:
    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def cape(name, fn):
    # Layout de capa do Minecraft: frente em (1,1)-(11,17), costas (12,1)-(22,17)
    def pixel(x, y):
        if x >= 22 or y >= 17:
            return (0, 0, 0, 0)
        u = (x % 11) / 10
        v = y / 16
        return (*fn(u, v, x, y), 255)
    png(OUT / f"{name}.png", 64, 32, pixel)


def wings(name, a, b):
    def pixel(x, y):
        # Uma asa: penas em degraus, transparente fora do formato
        edge = 31 - (x // 4) * 3
        if y > edge or x > 30:
            return (0, 0, 0, 0)
        c = mix(a, b, x / 31)
        if y % 6 == 5 or (y > edge - 2):
            c = mix(c, (0, 0, 0), .25)
        return (*c, 255)
    png(OUT / f"{name}.png", 32, 32, pixel)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logo = ["#####", "#....", "#....", "#####", "....#", "....#", "#####"]
    cape("cape_spk", lambda u, v, x, y: (232, 232, 232) if 5 <= y <= 11 and 3 <= x % 11 <= 7 and
         logo[y - 5][x % 11 - 3] == "#" else (30, 30, 30))
    cape("cape_ember", lambda u, v, x, y: mix((255, 200, 40), (180, 20, 10), v))
    cape("cape_ocean", lambda u, v, x, y: mix((20, 60, 160), (10, 20, 60), v) if (x + y // 3) % 5
         else (90, 170, 255))
    cape("cape_toxic", lambda u, v, x, y: (60, 255, 80) if (x + y) % 6 < 2 else (15, 40, 20))
    cape("cape_royal", lambda u, v, x, y: (230, 190, 60) if y in (1, 15) or x % 11 in (0, 10)
         else mix((90, 30, 150), (40, 10, 80), v))
    cape("cape_brasil", lambda u, v, x, y: (40, 70, 200) if (u - .5) ** 2 + (v - .5) ** 2 < .05
         else (250, 220, 40) if abs(u - .5) + abs(v - .5) < .45 else (20, 150, 60))
    wings("wings_angel", (255, 255, 255), (200, 215, 235))
    wings("wings_demon", (120, 10, 10), (40, 0, 0))
    wings("wings_dragon", (140, 60, 200), (50, 15, 90))


if __name__ == "__main__":
    main()
