#!/usr/bin/env python3

import pygame
import freetype
import numpy as np
import ctypes
import io
import cairosvg
import cairosvg.parser
from cairosvg.surface import SVGSurface, PNGSurface
import cairocffi as cairo


# These were added in a later version
if not hasattr(freetype.ft_structs, 'FT_SVG_Document') and freetype.version() >= (2, 10, 0):
    from ctypes import POINTER

    freetype.FT_PIXEL_MODE_BGRA = 7
    freetype.FT_GLYPH_FORMAT_SVG = int.from_bytes('SVG '.encode('ascii'), byteorder='big')
    freetype.FT_LOAD_NO_SVG = (1 << 24)
    def get_glyph_index(glyph):
        return glyph._FT_GlyphSlot.contents.reserved

    class FT_SVG_DocumentRec(ctypes.Structure):
        _fields_ = [
            ("svg_document",          POINTER(freetype.ft_structs.FT_Byte)),
            ("svg_document_length",   freetype.ft_structs.FT_ULong),
    
            ("metrics",               freetype.ft_structs.FT_Size_Metrics),
            ("units_per_EM",          freetype.ft_structs.FT_UShort),
    
            ("start_glyph_id",        freetype.ft_structs.FT_UShort),
            ("end_glyph_id",          freetype.ft_structs.FT_UShort),
    
            ("transform",             freetype.ft_structs.FT_Matrix),
            ("delta",                 freetype.ft_structs.FT_Vector),
        ]
    freetype.ft_structs.FT_SVG_Document = ctypes.POINTER(FT_SVG_DocumentRec)
else:
    def get_glyph_index(glyph):
        return glyph._FT_GlyphSlot.contents.glyph_index


class RecordingSurface(SVGSurface):
    surface_class = lambda self, output, width, height: cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, (0, 0, width, height))


def load_font(font_path, size):
    """Load a font and return the freetype Face object."""
    # Load the font
    face = freetype.Face(font_path)

    # Get available fixed sizes if any
    if face.available_sizes:
        face.set_char_size(int(face.available_sizes[-1].size))
    elif face.is_scalable:
        face.set_pixel_sizes(size, size)  # width and height in pixels
    else:
        print("Font is not scalable and has no available sizes.")
        exit(1)
    return face


def get_svg_tree(glyph):
    svg_doc = ctypes.cast(glyph._FT_GlyphSlot.contents.other, freetype.ft_structs.FT_SVG_Document).contents
    glyph_index = get_glyph_index(glyph)
    tree = cairosvg.parser.Tree(bytestring=ctypes.string_at(svg_doc.svg_document, svg_doc.svg_document_length))
    if svg_doc.start_glyph_id != svg_doc.end_glyph_id:
        # Find the glyph we care about. Keep 'defs' but discard everything else but it and our glyph. This is slow for large files.
        id_ = f'glyph{glyph_index}'
        new_children = []
        for node in tree.children:
            if node.tag == 'defs':
                new_children.append(node)
            if node.tag == 'g' and node.get('id') == id_:
                new_children.append(node)
                break
        tree.children = new_children
    return tree


def render_glyph(face: freetype.Face, index=None, code_point=None, char=None):
    if char is not None:
        code_point = ord(char)
    if code_point is not None:
        index = face.get_char_index(code_point)
    if index is not None:
        face.load_glyph(index, freetype.FT_LOAD_COLOR)
    glyph : freetype.GlyphSlot = face.glyph
    if glyph is None:
        print(f"Glyph for codepoint not found in font.")
        return None
    if glyph.format == freetype.FT_GLYPH_FORMAT_BITMAP or glyph.format == freetype.FT_GLYPH_FORMAT_OUTLINE:
        glyph.render(freetype.FT_RENDER_MODE_NORMAL)
        # Render the glyph onto the surface
        bitmap = glyph.bitmap
        # Check bitmap format
        if bitmap.rows == 0 or bitmap.width == 0:
            return None
        if bitmap.pixel_mode == freetype.FT_PIXEL_MODE_GRAY:
            # Single channel (grayscale)
            bitmap_array = np.array(bitmap.buffer, dtype=np.uint8).reshape((bitmap.width, bitmap.rows))
            # Convert to RGBA, where the pixel "color" is the opacity
            bitmap_array = np.stack([np.full_like(bitmap_array, 255)] * 3 + [bitmap_array], axis=-1)
        elif bitmap.pixel_mode == freetype.FT_PIXEL_MODE_BGRA:
            # 4 channels (BGRA)
            bitmap_array = np.array(bitmap.buffer, dtype=np.uint8).reshape((bitmap.width, bitmap.rows, 4))
            bitmap_array[:, :, [0, 2]] = bitmap_array[:, :, [2, 0]]  # BGRA to RGBA
        else:
            print(f"Unsupported pixel mode: {bitmap.pixel_mode}")
            return None
        return pygame.image.frombuffer(bitmap_array.flatten(), (bitmap.width, bitmap.rows), 'RGBA')
    elif glyph.format == freetype.FT_GLYPH_FORMAT_SVG:
        # SVG glyph: try to obtain the SVG data and rasterize it to a PNG, then blit into the surface.
        svg_doc = ctypes.cast(glyph._FT_GlyphSlot.contents.other, freetype.ft_structs.FT_SVG_Document).contents
        tree = get_svg_tree(glyph)
        l, t, w, h = face.bbox.xMin, -face.bbox.yMax, (face.bbox.xMax - face.bbox.xMin), (face.bbox.yMax - face.bbox.yMin)
        scale = face.size.x_ppem / face.units_per_EM
        # Chang the bitmap_left and bitmap_top to account for the glyph's position
        glyph._FT_GlyphSlot.contents.bitmap_left = int(l * scale)
        glyph._FT_GlyphSlot.contents.bitmap_top = -int(t * scale)

        tree['viewBox'] = f"{l} {t} {w} {h}"
        scale = svg_doc.metrics.x_ppem / svg_doc.units_per_EM
        png_surface = PNGSurface(tree, io.BytesIO(), scale=scale, dpi=96)
        png_surface.finish()
        png_surface.output.seek(0)
        return pygame.image.load(png_surface.output)
    else:
        glyph_index = get_glyph_index(glyph)
        print(f"Glyph format is not bitmap for index {glyph_index}: {glyph.format.to_bytes(4, 'big').decode('ascii')}")
        return None


class Font:
    def __init__(self, font_path, size):
        self.face = load_font(font_path, size)
        self.size = size
        if self.face.x_ppem != self.size:
            self.scale_factor = min(size / self.face.x_ppem, size / self.face.x_ppem)
        else:
            self.scale_factor = None

    def render_glyph(self, index=None, code_point=None, char=None):
        surface = render_glyph(self.face, index, code_point, char)
        if self.scale_factor is not None:
            surface = pygame.transform.smoothscale_by(surface, self.scale_factor)
        return surface