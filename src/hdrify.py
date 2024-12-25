"""
https://github.com/gky99/ssaHdrify
"""

import re
import ass as ssa
from io import StringIO
import numpy
from colour import RGB_Colourspace
from colour.models import eotf_inverse_BT2100_PQ, sRGB_to_XYZ, XYZ_to_xyY, xyY_to_XYZ, XYZ_to_RGB, \
    RGB_COLOURSPACE_BT2020, eotf_BT2100_PQ

COLOURSPACE_BT2100_PQ = RGB_Colourspace(
    name='COLOURSPACE_BT2100',
    primaries=RGB_COLOURSPACE_BT2020.primaries,
    whitepoint=RGB_COLOURSPACE_BT2020.whitepoint,
    matrix_RGB_to_XYZ=RGB_COLOURSPACE_BT2020.matrix_RGB_to_XYZ,
    matrix_XYZ_to_RGB=RGB_COLOURSPACE_BT2020.matrix_XYZ_to_RGB,
    cctf_encoding=eotf_inverse_BT2100_PQ,
    cctf_decoding=eotf_BT2100_PQ,
)


def ssaProcessor(assText: str, srgb_brightness=100):
    sub = ssa.parse_string(assText)
    for s in sub.styles:
        transformColour(s.primary_color, srgb_brightness)
        transformColour(s.secondary_color, srgb_brightness)
        transformColour(s.outline_color, srgb_brightness)
        transformColour(s.back_color, srgb_brightness)
    for e in sub.events:
        transformEvent(e, srgb_brightness)

    out = StringIO()
    sub.dump_file(out)
    return out.getvalue()

    # output_fname = os.path.splitext(fname)
    # output_fname = output_fname[0] + ".hdr.ass"

    # with open(output_fname, "w", encoding="utf_8_sig") as f:
    #     sub.dump_file(f)
    #     print(f"Wrote {output_fname}")


def transformColour(colour, srgb_brightness):
    rgb = (colour.r, colour.g, colour.b)
    transformed = sRgbToHdr(rgb, srgb_brightness)
    colour.r = transformed[0]
    colour.g = transformed[1]
    colour.b = transformed[2]


color_code_pattern = re.compile(r"\\[0-9]?c&H([0-9a-fA-F]{2,})&")
def transformEvent(event, srgb_brightness):
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
        (r, g, b) = sRgbToHdr((r, g, b), srgb_brightness)
        hex_colour = "{:02x}{:02x}{:02x}".format(b, g, r)
        matches.append((start, end, hex_colour.upper()))

    for start, end, hex_colour in matches:
        line = line[:start] + hex_colour + line[end:]

    event.text = line


def sRgbToHdr(source: tuple[int, int, int], srgb_brightness) -> tuple[int, int, int]:
    """
    Convert RGB color in SDR color space to HDR color space.

    How it works:
    1. Convert the RGB color to reference xyY color space to get absolute chromaticity and linear luminance response
    2. Time the target brightness of SDR color space to the Y because Rec.2100 has an absolute luminance
    3. Convert the xyY color back to RGB under Rec.2100/Rec.2020 color space.

    Notes:
    -  Unlike sRGB and Rec.709 color space which have their OOTF(E) = EOTF(OETF(E)) equals or almost equals to y = x,
        it's OOTF is something close to gamma 2.4. Therefore, to have matched display color for color in SDR color space
        the COLOURSPACE_BT2100_PQ denotes a display color space rather than a scene color space. It wasted me quite some
        time to figure that out :(
    -  Option to set output luminance is removed because PQ has an absolute luminance level, which means any color in
        the Rec.2100 color space will be displayed the same on any accurate display regardless of the capable peak
        brightness of the device if no clipping happens. Therefore, the peak brightness should always target 10000 nits
        so the SDR color can be accurately projected to the sub-range of Rec.2100 color space
    args:
    colour -- (0-255, 0-255, 0-255)
    """
    normalized_sdr_color = numpy.array(source) / 255
    xyY_sdr_color = XYZ_to_xyY(
        sRGB_to_XYZ(normalized_sdr_color, apply_cctf_decoding=True)
    )

    xyY_hdr_color = xyY_sdr_color.copy()
    target_luminance = xyY_sdr_color[2] * srgb_brightness
    xyY_hdr_color[2] = target_luminance

    output = XYZ_to_RGB(
        xyY_to_XYZ(xyY_hdr_color),
        colourspace=COLOURSPACE_BT2100_PQ,
        apply_cctf_encoding=True,
    )
    output = numpy.round(output * 255)
    return (int(output[0]), int(output[1]), int(output[2]))
