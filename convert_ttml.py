import ctypes
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache

# Existing configurations...
PLAY_RES_X = 1280
PLAY_RES_Y = 720
BASE_FS = 54
RUBY_FS = 26
FONT_NAME = "BIZ UDPGothic"
...existing configurations...

def append_tatechuyoko_dialogue(ass_lines, layer, start, end, x, y, size, text, style_tag):
    """
    Add a tatechuyoko dialogue line to ASS file.
    """
    prefix = rf"{{\an5\pos({x:.1f},{y:.1f})\fs{size}\q2}}"
    ass_lines.append(
        f"Dialogue: {layer},{start},{end},Default,,0,0,0,,{prefix}{style_tag}{escape_ass_text(text)}"
    )

def handle_tatechuyoko_lines(ass_lines, layer, start, end, lines):
    """
    Handle vertical tatechuyoko-specific rendering logic.
    """
    for line_index, line_parts in enumerate(lines):
        for part in line_parts:
          #---tcys---collapse
