"""用 Python 标准库提取带 ToUnicode 映射的 PDF 布局文本。

用于归档省级财政公开表的可复核文本捕获；不做 OCR，不对无法解码的字形
进行猜测。支持常见的 FlateDecode 以及 PDF 1.5 object stream。
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path


OBJECT_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)(?:endobj)", re.S)
TOKEN_RE = re.compile(
    r"/(\w+)\s+[\d.]+\s+Tf|"
    r"([\d.-]+)\s+0\s+0\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+Tm|"
    r"([\d.-]+)\s+([\d.-]+)\s+TD|"
    r"\[(.*?)\]\s*TJ|"
    r"<([0-9A-Fa-f]+)>\s*Tj|\((.*?)\)\s*Tj",
    re.S,
)


def _stream(body: bytes) -> bytes:
    raw = body.split(b"stream", 1)[1].lstrip(b"\r\n")
    raw = raw.rsplit(b"endstream", 1)[0].rstrip(b"\r\n")
    return zlib.decompress(raw) if b"/FlateDecode" in body else raw


def _objects(data: bytes) -> dict[int, bytes]:
    objects = {int(match.group(1)): match.group(3) for match in OBJECT_RE.finditer(data)}
    for body in list(objects.values()):
        if b"/Type/ObjStm" not in body:
            continue
        try:
            decoded = _stream(body)
        except zlib.error:
            continue
        count = int(re.search(rb"/N\s+(\d+)", body).group(1))
        first = int(re.search(rb"/First\s+(\d+)", body).group(1))
        pairs = list(map(int, re.findall(rb"\d+", decoded[:first])))
        for index in range(0, 2 * count, 2):
            object_number, offset = pairs[index : index + 2]
            next_offset = pairs[index + 3] if index + 3 < len(pairs) else len(decoded) - first
            objects[object_number] = decoded[first + offset : first + next_offset]
    return objects


def _cmap(objects: dict[int, bytes], object_number: int) -> dict[int, str]:
    try:
        text = _stream(objects[object_number]).decode("latin1")
    except (KeyError, IndexError, ValueError, zlib.error):
        return {}
    mapping: dict[int, str] = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for source, target in re.findall(r"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>", block):
            try:
                mapping[int(source, 16)] = bytes.fromhex(target).decode("utf-16-be")
            except UnicodeDecodeError:
                continue
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for start, end, target in re.findall(
            r"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>", block
        ):
            for code in range(int(start, 16), int(end, 16) + 1):
                mapping[code] = chr(int(target, 16) + code - int(start, 16))
    return mapping


def _decode_hex(value: str, mapping: dict[int, str]) -> str:
    value = re.sub(r"[^0-9A-Fa-f]", "", value)
    return "".join(mapping.get(int(value[index : index + 4], 16), "") for index in range(0, len(value) - 3, 4))


def _decode_literal(value: str) -> str:
    """Decode literal PDF strings, including UTF-16BE strings emitted by iText.

    Some Chinese government PDFs do not expose a usable ToUnicode CMap but do
    write each literal text string as a UTF-16BE byte sequence.  Returning the
    raw Latin-1 representation makes an otherwise text-readable PDF appear as
    mojibake and prevents downstream row parsing.
    """
    raw = value.encode("latin1")
    if len(raw) % 2 == 0 and (b"\x00" in raw or raw.startswith(b"\xfe\xff")):
        try:
            decoded = raw.decode("utf-16-be")
            if decoded:
                return decoded
        except UnicodeDecodeError:
            pass
    return value


def extract_pdf_text(path: Path) -> str:
    objects = _objects(path.read_bytes())
    mappings: dict[int, dict[int, str]] = {}
    for object_number, body in objects.items():
        match = re.search(rb"/Subtype/Type0.*?/ToUnicode\s+(\d+)\s+0\s+R", body, re.S)
        if match:
            mappings[object_number] = _cmap(objects, int(match.group(1)))

    pages: list[tuple[int, int, dict[str, int]]] = []
    for object_number, body in sorted(objects.items()):
        if b"/Type/Page" not in body or b"/Type/Pages" in body:
            continue
        content_match = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        resource_match = re.search(rb"/Resources\s+(\d+)\s+0\s+R", body)
        if not content_match:
            continue
        resources = objects.get(int(resource_match.group(1))) if resource_match else body
        fonts = {
            name.decode(): int(font_number)
            for name, font_number in re.findall(rb"/(\w+)\s+(\d+)\s+0\s+R", resources or b"")
        }
        pages.append((object_number, int(content_match.group(1)), fonts))

    page_text: list[str] = []
    for _, content_number, fonts in pages:
        try:
            content = _stream(objects[content_number]).decode("latin1")
        except (KeyError, UnicodeDecodeError, zlib.error):
            page_text.append("")
            continue
        font = None
        x = y = 0.0
        scale_x = scale_y = 1.0
        events: list[tuple[float, float, str]] = []
        for match in TOKEN_RE.finditer(content):
            groups = match.groups()
            if groups[0]:
                font = fonts.get(groups[0])
            elif groups[1] is not None:
                scale_x, scale_y = float(groups[1]), float(groups[2])
                x, y = float(groups[3]), float(groups[4])
            elif groups[5] is not None:
                x += float(groups[5]) * scale_x
                y += float(groups[6]) * scale_y
            else:
                if groups[7] is not None:
                    text = "".join(
                        _decode_hex(value, mappings.get(font, {}))
                        for value in re.findall(r"<([0-9A-Fa-f]+)>", groups[7])
                    )
                else:
                    raw = groups[8] if groups[8] is not None else groups[9]
                    text = _decode_hex(raw, mappings.get(font, {})) if groups[8] is not None else _decode_literal(raw)
                if text.strip():
                    events.append((y, x, text))
        events.sort()
        lines: list[tuple[float, list[tuple[float, str]]]] = []
        for y_value, x_value, text in events:
            if not lines or abs(lines[-1][0] - y_value) > 1.0:
                lines.append((y_value, [(x_value, text)]))
            else:
                lines[-1][1].append((x_value, text))
        output_lines: list[str] = []
        for _, items in lines:
            groups: list[list[tuple[float, str]]] = []
            for x_value, text in sorted(items):
                if not groups or x_value - groups[-1][-1][0] > 15:
                    groups.append([(x_value, text)])
                else:
                    groups[-1].append((x_value, text))
            output_lines.append("  ".join("".join(text for _, text in group) for group in groups))
        page_text.append("\n".join(output_lines))
    return "\f\n".join(page_text)


if __name__ == "__main__":
    sys.stdout.write(extract_pdf_text(Path(sys.argv[1])))
