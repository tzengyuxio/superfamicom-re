"""kaodata/1 primitives shared by the game exporters: reference renderer (spec §6), checksums (§8), I/O.

Spec: docs/data-format.md of the kaodata website repo.
"""
import hashlib
import json
import os
import subprocess
import zlib

FORMAT = "kaodata/1"
TRANSPARENT = 255


def get_image(meta: dict, blobs: list[bytes], img: int) -> tuple[int, int, bytes]:
    offset, w, h, *rest = meta["images"][img]
    pixels = blobs[rest[0] if rest else 0]
    return w, h, pixels[offset:offset + w * h]


def blit(dst: bytearray, dw: int, dh: int, src: tuple[int, int, bytes], x: int, y: int) -> None:
    sw, sh, data = src
    for sy in range(sh):
        dy = y + sy
        if not 0 <= dy < dh:
            continue
        for sx in range(sw):
            dx = x + sx
            c = data[sy * sw + sx]
            if 0 <= dx < dw and c != TRANSPARENT:
                dst[dy * dw + dx] = c


def crop(src: tuple[int, int, bytes], rect) -> tuple[int, int, bytes]:
    sw, sh, data = src
    x, y, w, h = rect
    out = bytearray([TRANSPARENT]) * (w * h)
    for row in range(h):
        if 0 <= y + row < sh:
            for col in range(w):
                if 0 <= x + col < sw:
                    out[row * w + col] = data[(y + row) * sw + x + col]
    return w, h, bytes(out)


def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    """Indexed display image of a character's face (spec §6, without backgrounds)."""
    if "portrait" in face:
        pt = meta["portraits"][face["portrait"]]
        shown = get_image(meta, blobs, pt["img"])
        return crop(shown, pt["window"]) if "window" in pt else shown
    comp = meta["composite"]
    variant = comp["variants"][face["variant"]]
    cw, ch = comp["canvas"]
    canvas = bytearray([TRANSPARENT]) * (cw * ch)
    for slot, part in zip(comp["slots"], face["parts"]):
        sp = variant["parts"][slot["id"]]
        item = sp["items"][part]
        img, (x, y) = (item, sp.get("at", [0, 0])) if isinstance(item, int) else (item["img"], item["at"])
        blit(canvas, cw, ch, get_image(meta, blobs, img), x, y)
    shown = (cw, ch, bytes(canvas))
    return crop(shown, variant["window"]) if "window" in variant else shown


def to_rgba(src: tuple[int, int, bytes], colors: list[str]) -> bytes:
    rgb = [bytes.fromhex(c[1:]) for c in colors]
    return b"".join(b"\0\0\0\0" if c == TRANSPARENT else rgb[c] + b"\xff" for c in src[2])


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{c['id']}": digest(c["face"]) for c in meta["characters"] if "face" in c}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta.get("portraits", [])))})
    return {"algo": "sha256-rgba", "entries": entries}


def write_dataset(out_dir: str, meta: dict, blobs: list[bytes]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, px in zip(meta["blobs"], blobs):
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(comp.compress(px) + comp.flush())
    with open(os.path.join(out_dir, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "checksums.json"), "w", encoding="utf-8") as f:
        json.dump(checksums(meta, blobs), f, indent=1)


def load_dataset(out_dir: str) -> tuple[dict, list[bytes]]:
    with open(os.path.join(out_dir, "dataset.json"), encoding="utf-8") as f:
        meta = json.load(f)
    blobs = []
    for name in meta.get("blobs", ["pixels.bin"]):
        with open(os.path.join(out_dir, name), "rb") as f:
            blobs.append(zlib.decompress(f.read(), -15))
    return meta, blobs


def revision(repo: str) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True, cwd=repo).stdout.strip()


def hiragana(s: str) -> str:
    """Katakana (full- or half-width) -> hiragana."""
    import unicodedata
    s = unicodedata.normalize("NFKC", s)
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
