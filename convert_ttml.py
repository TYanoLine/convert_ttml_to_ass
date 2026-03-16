import ctypes
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache


# ASS 出力時の基本レイアウト設定。
PLAY_RES_X = 1280
PLAY_RES_Y = 720
BASE_FS = 54
RUBY_FS = 26
FONT_NAME = "BIZ UDPGothic"
GLOBAL_MARGIN_V = 100
LINE_HEIGHT = 64
RUBY_GAP = 6
TTS_NS = "http://www.w3.org/ns/ttml#styling"
XML_NS = "http://www.w3.org/XML/1998/namespace"
VERTICAL_CHAR_MAP = {
    "…": "︙",
    "‥": "︰",
    "「": "﹁",
    "」": "﹂",
    "『": "﹃",
    "』": "﹄",
    "（": "︵",
    "）": "︶",
    "［": "﹇",
    "］": "﹈",
    "｛": "︷",
    "｝": "︸",
    "〈": "︿",
    "〉": "﹀",
    "《": "︽",
    "》": "︾",
    "【": "︻",
    "】": "︼",
    "“": "﹁",
    "”": "﹂",
}
VERTICAL_ROTATE_CHARS = {"ー", "―", "-", "‐", "〜", "～"}
VERTICAL_ROTATE_OFFSET_X = 4
VERTICAL_ROTATE_OFFSET_Y = 9
VERTICAL_NON_ITALIC_CHARS = set(VERTICAL_CHAR_MAP) | VERTICAL_ROTATE_CHARS | {"・", "･", "︙", "︰"}
VERTICAL_CHAR_OFFSET_MAP = {
    "「": (5, 0),
    "“": (5, 0),
}


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class TextMeasurer:
    DEFAULT_CHARSET = 1
    OUT_TT_PRECIS = 4
    CLIP_DEFAULT_PRECIS = 0
    CLEARTYPE_QUALITY = 5
    DEFAULT_PITCH = 0
    FF_DONTCARE = 0

    def __init__(self, font_name):
        # Windows GDI を使って文字列幅を実測し、ルビの配置計算に使う。
        self.font_name = font_name
        self.dc = ctypes.windll.gdi32.CreateCompatibleDC(0)
        if not self.dc:
            raise ctypes.WinError()
        self.fonts = {}

    def close(self):
        for font in self.fonts.values():
            ctypes.windll.gdi32.DeleteObject(font)
        self.fonts.clear()
        if self.dc:
            ctypes.windll.gdi32.DeleteDC(self.dc)
            self.dc = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _get_font(self, size, italic):
        # サイズと斜体有無ごとにフォントを再利用して GDI オブジェクト生成を抑える。
        key = (size, italic)
        if key not in self.fonts:
            font = ctypes.windll.gdi32.CreateFontW(
                -int(round(size)),
                0,
                0,
                0,
                400,
                1 if italic else 0,
                0,
                0,
                self.DEFAULT_CHARSET,
                self.OUT_TT_PRECIS,
                self.CLIP_DEFAULT_PRECIS,
                self.CLEARTYPE_QUALITY,
                self.DEFAULT_PITCH | self.FF_DONTCARE,
                self.font_name,
            )
            if not font:
                raise ctypes.WinError()
            self.fonts[key] = font
        return self.fonts[key]

    @lru_cache(maxsize=4096)
    def measure(self, text, size, italic=False):
        # 同じ文字列の計測結果はキャッシュしてレイアウト計算を軽くする。
        if not text:
            return 0

        font = self._get_font(size, italic)
        old_font = ctypes.windll.gdi32.SelectObject(self.dc, font)
        extent = SIZE()
        ok = ctypes.windll.gdi32.GetTextExtentPoint32W(
            self.dc,
            text,
            len(text),
            ctypes.byref(extent),
        )
        ctypes.windll.gdi32.SelectObject(self.dc, old_font)
        if not ok:
            raise ctypes.WinError()
        return extent.cx


def escape_ass_text(text):
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def get_vertical_char_text(char):
    # 縦書き用に字形差し替えが必要な文字と、90 度回転が必要な文字を処理する。
    glyph = VERTICAL_CHAR_MAP.get(char, char)
    rotation_tag = r"\frz90" if char in VERTICAL_ROTATE_CHARS else ""
    return glyph, rotation_tag


def get_vertical_char_style_tag(char, italic, font_shear):
    if char in VERTICAL_NON_ITALIC_CHARS:
        return build_ass_style_tag(disable_italic=True, font_shear=font_shear)
    return build_ass_style_tag(italic=italic, font_shear=font_shear)


def get_vertical_char_offsets(char, rotation_tag):
    # 一部の約物は縦書き時に見た目がずれるため、個別オフセットを足す。
    offset_x, offset_y = VERTICAL_CHAR_OFFSET_MAP.get(char, (0, 0))
    if rotation_tag:
        offset_x += VERTICAL_ROTATE_OFFSET_X
        offset_y += VERTICAL_ROTATE_OFFSET_Y
    return offset_x, offset_y


def parse_time_seconds(value):
    if not value:
        return 0
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_time_seconds(total_seconds):
    adjusted_seconds = max(total_seconds, 0)
    return (
        f"{int(adjusted_seconds // 3600)}:"
        f"{int((adjusted_seconds % 3600) // 60):02d}:"
        f"{adjusted_seconds % 60:05.2f}"
    )


def collect_ruby_styles(root, ns):
    # style 定義からルビ関連のスタイル ID を収集しておく。
    ruby_styles = {"container": set(), "base": set(), "text": set()}
    for style in root.findall(".//tt:style", ns):
        style_id = style.get(f"{{{XML_NS}}}id")
        ruby_type = style.get(f"{{{TTS_NS}}}ruby")
        if not style_id or not ruby_type:
            continue
        if ruby_type in ruby_styles:
            ruby_styles[ruby_type].add(style_id)
    return ruby_styles


def collect_style_definitions(root, ns):
    # 斜体やシアーなどの見た目判定に使う style 定義を参照しやすい形へまとめる。
    style_definitions = {}
    for style in root.findall(".//tt:style", ns):
        style_id = style.get(f"{{{XML_NS}}}id")
        if not style_id:
            continue
        style_definitions[style_id] = {
            "font_style": style.get(f"{{{TTS_NS}}}fontStyle"),
            "font_shear": style.get(f"{{{TTS_NS}}}fontShear"),
            "style_refs": style.get("style", "").split(),
        }
    return style_definitions


def resolve_style_property(style_id, style_definitions, property_name, seen=None):
    if seen is None:
        seen = set()
    if style_id in seen:
        return None
    seen.add(style_id)

    style_definition = style_definitions.get(style_id)
    if style_definition is None:
        return None

    property_value = style_definition[property_name]
    if property_value:
        return property_value

    for parent_style_id in style_definition["style_refs"]:
        inherited_value = resolve_style_property(parent_style_id, style_definitions, property_name, seen)
        if inherited_value:
            return inherited_value
    return None


def parse_font_shear(font_shear):
    if not font_shear:
        return 0.0
    if font_shear.endswith("%"):
        return -float(font_shear[:-1]) / 100
    return -float(font_shear)


def resolve_element_style(elem, style_definitions):
    # 要素自身の指定を優先し、なければ参照 style をたどって fontStyle / fontShear を解決する。
    font_style = elem.get(f"{{{TTS_NS}}}fontStyle")
    font_shear = elem.get(f"{{{TTS_NS}}}fontShear")

    for style_id in elem.get("style", "").split():
        if not font_style:
            font_style = resolve_style_property(style_id, style_definitions, "font_style")
        if not font_shear:
            font_shear = resolve_style_property(style_id, style_definitions, "font_shear")

    return {
        "italic": font_style == "italic",
        "font_shear": parse_font_shear(font_shear),
    }


def build_ass_style_tag(italic=False, font_shear=0.0, disable_italic=False):
    commands = []
    if disable_italic:
        commands.append(r"\i0")
    elif italic or font_shear:
        commands.append(r"\i1")
    if font_shear:
        commands.append(rf"\fax{font_shear:.4f}")
    return "{" + "".join(commands) + "}" if commands else ""


def find_first_descendant_with_style(elem, style_ids):
    for child in elem.iter():
        if child is elem:
            continue
        if child.get("style") in style_ids:
            return child
    return None


def get_all_parts(elem, ns, ruby_styles):
    # TTML の p 要素配下を、通常文字列・改行・ルビ付き文字列の並びへ平坦化する。
    parts = []
    if elem.text:
        parts.append(("text", elem.text))

    for child in elem:
        if child.get("style") in ruby_styles["container"]:
            base = find_first_descendant_with_style(child, ruby_styles["base"])
            ruby = find_first_descendant_with_style(child, ruby_styles["text"])
            if base is not None and ruby is not None:
                parts.append(
                    (
                        "ruby",
                        (
                            base.text if base.text else "",
                            ruby.text if ruby.text else "",
                        ),
                    )
                )
            else:
                parts.extend(get_all_parts(child, ns, ruby_styles))
        elif child.tag.endswith("br"):
            parts.append(("br", None))
        else:
            parts.extend(get_all_parts(child, ns, ruby_styles))

        if child.tail:
            parts.append(("text", child.tail))
    return parts


def split_lines(parts):
    # br を境に ASS の行単位へ分割する。
    lines = [[]]
    for part in parts:
        if part[0] == "br":
            lines.append([])
            continue
        lines[-1].append(part)
    return lines


def base_text(part):
    if part[0] == "ruby":
        return part[1][0]
    return part[1]


def plain_text(parts):
    return "".join(base_text(part) for part in parts)


def has_ruby(parts):
    return any(part[0] == "ruby" for part in parts)


def get_ruby_line_positions(lines):
    # 下の行にルビがある場合は、その分だけ上の行を追加で押し上げて重なりを防ぐ。
    if not lines:
        return []

    ruby_line_height = BASE_FS + RUBY_FS + RUBY_GAP
    positions = [0.0] * len(lines)
    current_y = PLAY_RES_Y - GLOBAL_MARGIN_V

    for line_index in range(len(lines) - 1, -1, -1):
        positions[line_index] = current_y
        if line_index == 0:
            continue

        line_gap = LINE_HEIGHT
        if has_ruby(lines[line_index]):
            line_gap = max(line_gap, ruby_line_height)
        current_y -= line_gap

    return positions


def get_vertical_line_positions(lines, start_x, column_step):
    # ルビ付きの列は右側にルビ領域を使うので、左隣の列との間隔を広げる。
    if not lines:
        return []

    ruby_column_step = BASE_FS + RUBY_GAP + RUBY_FS
    positions = [0.0] * len(lines)
    positions[0] = start_x

    for line_index in range(1, len(lines)):
        gap = ruby_column_step if has_ruby(lines[line_index]) else column_step
        positions[line_index] = positions[line_index - 1] - gap

    return positions


def append_vertical_dialogue(ass_lines, layer, start, end, x, y, text, style_tag, font_size=None, rotation_tag=""):
    prefix = rf"{{\an5\pos({x:.1f},{y:.1f})"
    if font_size is not None:
        prefix += rf"\fs{font_size}"
    prefix += rotation_tag + "}"
    ass_lines.append(
        f"Dialogue: {layer},{start},{end},Default,,0,0,0,,"
        f"{prefix}{style_tag}{escape_ass_text(text)}"
    )


def render_standard_dialogue(ass_lines, start, end, style_name, style_tag, parts):
    text = "".join(
        escape_ass_text(base_text(part)) if part[0] != "br" else r"\N"
        for part in parts
    )
    ass_lines.append(f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{style_tag}{text}")


def render_positioned_ruby_dialogues(
    ass_lines,
    measurer,
    start,
    end,
    italic,
    style_tag,
    lines,
):
    # ルビ付き行はベース文字列を中央配置し、その上にルビを個別配置する。
    layer = 0
    center_x = PLAY_RES_X / 2
    line_positions = get_ruby_line_positions(lines)

    for line_index, line_parts in enumerate(lines):
        line_y = line_positions[line_index]
        visible_line = escape_ass_text(plain_text(line_parts))
        ass_lines.append(
            f"Dialogue: {layer},{start},{end},Default,,0,0,0,,"
            f"{{\\an2\\pos({center_x:.1f},{line_y:.1f})}}{style_tag}{visible_line}"
        )

        line_width = measurer.measure(plain_text(line_parts), BASE_FS, italic)
        cursor_x = center_x - line_width / 2

        for part in line_parts:
            if part[0] == "text":
                cursor_x += measurer.measure(part[1], BASE_FS, italic)
                continue

            base, ruby = part[1]
            base_width = measurer.measure(base, BASE_FS, italic)
            ruby_center_x = cursor_x + base_width / 2
            ruby_top_y = line_y - BASE_FS - RUBY_FS - RUBY_GAP
            ass_lines.append(
                f"Dialogue: {layer + 1},{start},{end},Default,,0,0,0,,"
                f"{{\\an8\\pos({ruby_center_x:.1f},{ruby_top_y:.1f})\\fs{RUBY_FS}}}"
                f"{style_tag}{escape_ass_text(ruby)}"
            )
            layer += 1
            cursor_x += base_width

        layer += 1


def render_positioned_vertical_dialogues(ass_lines, start, end, italic, font_shear, lines):
    # 縦書きは 1 文字ずつ絶対配置して、記号ごとの補正もここで反映する。
    region_top = PLAY_RES_Y * 0.1
    region_height = PLAY_RES_Y * 0.8
    region_right = PLAY_RES_X - PLAY_RES_X * 0.1
    start_x = region_right - BASE_FS / 2
    column_step = LINE_HEIGHT

    max_chars = max((len(plain_text(line_parts)) for line_parts in lines), default=1)
    char_step = min(BASE_FS, region_height / max_chars)
    start_y = region_top + max((region_height - max_chars * char_step) / 2, 0)
    line_positions = get_vertical_line_positions(lines, start_x, column_step)

    layer = 0
    for line_index, line_parts in enumerate(lines):
        line_x = line_positions[line_index]
        cursor_y = start_y
        for part in line_parts:
            if part[0] == "text":
                for char in part[1]:
                    if char == " ":
                        cursor_y += char_step
                        continue

                    glyph, rotation_tag = get_vertical_char_text(char)
                    char_style_tag = get_vertical_char_style_tag(char, italic, font_shear)
                    offset_x, offset_y = get_vertical_char_offsets(char, rotation_tag)
                    cell_center_x = line_x + offset_x
                    cell_center_y = cursor_y + char_step / 2 + offset_y
                    append_vertical_dialogue(
                        ass_lines,
                        layer,
                        start,
                        end,
                        cell_center_x,
                        cell_center_y,
                        glyph,
                        char_style_tag,
                        rotation_tag=rotation_tag,
                    )
                    layer += 1
                    cursor_y += char_step
                continue

            base, ruby = part[1]
            base_chars = [char for char in base if char != " "]
            base_span = max(len(base_chars), 1) * char_step
            base_start_y = cursor_y

            for char in base:
                if char == " ":
                    cursor_y += char_step
                    continue

                glyph, rotation_tag = get_vertical_char_text(char)
                char_style_tag = get_vertical_char_style_tag(char, italic, font_shear)
                offset_x, offset_y = get_vertical_char_offsets(char, rotation_tag)
                cell_center_x = line_x + offset_x
                cell_center_y = cursor_y + char_step / 2 + offset_y
                append_vertical_dialogue(
                    ass_lines,
                    layer,
                    start,
                    end,
                    cell_center_x,
                    cell_center_y,
                    glyph,
                    char_style_tag,
                    rotation_tag=rotation_tag,
                )
                layer += 1
                cursor_y += char_step

            ruby_chars = list(ruby)
            if not ruby_chars:
                continue

            ruby_step = min(RUBY_FS, base_span / len(ruby_chars))
            ruby_start_y = base_start_y + max((base_span - ruby_step * len(ruby_chars)) / 2, 0)
            ruby_x = line_x + BASE_FS / 2 + RUBY_GAP + RUBY_FS / 2
            ruby_style_tag = build_ass_style_tag(italic=italic, font_shear=font_shear)

            for ruby_index, ruby_char in enumerate(ruby_chars):
                glyph, rotation_tag = get_vertical_char_text(ruby_char)
                offset_x, offset_y = get_vertical_char_offsets(ruby_char, rotation_tag)
                ruby_center_y = ruby_start_y + ruby_step * ruby_index + ruby_step / 2 + offset_y
                append_vertical_dialogue(
                    ass_lines,
                    layer,
                    start,
                    end,
                    ruby_x + offset_x,
                    ruby_center_y,
                    glyph,
                    ruby_style_tag,
                    font_size=RUBY_FS,
                    rotation_tag=rotation_tag,
                )
                layer += 1


def convert_ttml_to_ass(ttml_input, ass_output, offset_seconds=0):
    # TTML を解析し、横書き・縦書き・ルビの各ケースに応じて ASS を組み立てる。
    ns = {
        "tt": "http://www.w3.org/ns/ttml",
        "tts": "http://www.w3.org/ns/ttml#styling",
        "ttp": "http://www.w3.org/ns/ttml#parameter",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }

    tree = ET.parse(ttml_input)
    root = tree.getroot()
    ruby_styles = collect_ruby_styles(root, ns)
    style_definitions = collect_style_definitions(root, ns)

    ass_lines = [
        "[Script Info]",
        "; Script generated by Copilot CLI & Gemini - Vertical Positioning Fix",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{FONT_NAME},{BASE_FS},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,{GLOBAL_MARGIN_V},1",
        f"Style: Vertical,@{FONT_NAME},{BASE_FS},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,1,0,0,100,100,0,0,1,2,2,8,10,10,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    body = root.find(".//tt:body", ns)
    if body is None:
        raise ValueError("TTML body not found")

    with TextMeasurer(FONT_NAME) as measurer:
        for p in body.findall(".//tt:p", ns):
            begin_seconds = parse_time_seconds(p.get("begin"))
            end_seconds = parse_time_seconds(p.get("end"))
            if end_seconds <= offset_seconds:
                continue

            start = format_time_seconds(begin_seconds - offset_seconds)
            end = format_time_seconds(end_seconds - offset_seconds)
            if start == end:
                continue

            region = p.get("region")
            style_name = "Vertical" if region == "縦右" else "Default"
            # 固定の style ID ではなく、TTML 側の fontStyle / fontShear 定義から判定する。
            resolved_style = resolve_element_style(p, style_definitions)
            italic = resolved_style["italic"]
            font_shear = resolved_style["font_shear"]
            style_tag = build_ass_style_tag(italic=italic, font_shear=font_shear)

            parts = get_all_parts(p, ns, ruby_styles)

            if style_name == "Vertical":
                render_positioned_vertical_dialogues(
                    ass_lines,
                    start,
                    end,
                    italic,
                    font_shear,
                    split_lines(parts),
                )
            elif not has_ruby(parts):
                render_standard_dialogue(ass_lines, start, end, style_name, style_tag, parts)
            else:
                render_positioned_ruby_dialogues(
                    ass_lines,
                    measurer,
                    start,
                    end,
                    italic,
                    style_tag,
                    split_lines(parts),
                )

    with open(ass_output, "w", encoding="utf_8") as output_file:
        output_file.write("\n".join(ass_lines))


if __name__ == "__main__":
    # 引数: offset, input.ttml, output.ass の順。未指定時はサンプル名を使う。
    offset = 0
    ttml_input = "sample.ttml"
    ass_output = "sample_offset.ass"
    if len(sys.argv) > 1:
        ts = sys.argv[1].split(":")
        offset = int(ts[0]) * 3600 + int(ts[1]) * 60 + float(ts[2])
    if len(sys.argv) > 2:
        ttml_input = sys.argv[2]
    if len(sys.argv) > 3:
        ass_output = sys.argv[3]

    convert_ttml_to_ass(ttml_input, ass_output, offset)
    print(f"Ruby conversion complete: {ass_output}")

