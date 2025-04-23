import colorsys
from io import StringIO
import re
import ass as ssa


def colorAdjust(rgb, sf=1.0, vf=1.0):
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
    # 调整亮度与饱和度
    s = min(max(s * sf, 0), 1)  # 饱和度范围 [0, 1]
    v = min(max(v * vf, 0), 1)  # 亮度范围 [0, 1]
    r_adj, g_adj, b_adj = colorsys.hsv_to_rgb(h, s, v)
    r_adj = round(r_adj * 255)
    g_adj = round(g_adj * 255)
    b_adj = round(b_adj * 255)
    return (r_adj, g_adj, b_adj)

def transformColour(colour, sf,vf):
    rgb = (colour.r, colour.g, colour.b)
    transformed = colorAdjust(rgb, sf,vf)
    colour.r = transformed[0]
    colour.g = transformed[1]
    colour.b = transformed[2]

color_code_pattern = re.compile(r"\\[0-9]?c&H([0-9a-fA-F]{2,})&")
def transformEvent(event, sf,vf):
    line = event.text
    matches = []
    for match in color_code_pattern.finditer(line):
        start = match.start(1)
        end = match.end(1)
        hex_colour = match.group(1)
        hex_colour.rjust(6, "0")
        b = int(hex_colour[0:2], 16)
        g = int(hex_colour[2:4], 16)
        r = int(hex_colour[4:6], 16)
        (r, g, b) = colorAdjust((r, g, b), sf,vf)
        hex_colour = "{:02x}{:02x}{:02x}".format(b, g, r)
        matches.append((start, end, hex_colour.upper()))
    for start, end, hex_colour in matches:
        line = line[:start] + hex_colour + line[end:]
    event.text = line

def ssaProcessor(assText: str, sf,vf):
    sub = ssa.parse_string(assText)
    for s in sub.styles:
        transformColour(s.primary_color, sf,vf)
        transformColour(s.secondary_color, sf,vf)
        transformColour(s.outline_color, sf,vf)
        transformColour(s.back_color, sf,vf)
    for e in sub.events:
        transformEvent(e, sf,vf)
    out = StringIO()
    sub.dump_file(out)
    return out.getvalue()




# r, g, b = 255, 0, 0  # 半透明红色
# brightness_factor = 1.5  # 增加亮度 50%
# adjusted_rgba = colorAdjust((r, g, b), 1, 0.5)
# print(f"原始 RGBA: R={r}, G={g}, B={b}")
# print(f"调整后 RGBA: R={adjusted_rgba[0]}, G={adjusted_rgba[1]}, B={adjusted_rgba[2]}")
