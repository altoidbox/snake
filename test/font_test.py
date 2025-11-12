#!/usr/bin/env python3

import pygame
import freetype
import numpy as np
import ctypes
import io
import cairosvg
import cairosvg.parser
import cairosvg.bounding_box
from cairosvg.surface import SVGSurface, PNGSurface
import cairocffi as cairo

import time

# These were added in a later version
# freetype.FT_PIXEL_MODE_BGRA = 7
# freetype.FT_GLYPH_FORMAT_SVG = int.from_bytes('SVG '.encode('ascii'))
# freetype.FT_LOAD_NO_SVG = (1 << 24)
# 
# class FT_SVG_DocumentRec(ctypes.Structure):
#     _fields_ = [
#         ("svg_document",          POINTER(freetype.ft_structs.FT_Byte)),
#         ("svg_document_length",   freetype.ft_structs.FT_ULong),
# 
#         ("metrics",               freetype.ft_structs.FT_Size_Metrics),
#         ("units_per_EM",          freetype.ft_structs.FT_UShort),
# 
#         ("start_glyph_id",        freetype.ft_structs.FT_UShort),
#         ("end_glyph_id",          freetype.ft_structs.FT_UShort),
# 
#         ("transform",             freetype.ft_structs.FT_Matrix),
#         ("delta",                 freetype.ft_structs.FT_Vector),
#     ]
# FT_SVG_Document = ctypes.POINTER(FT_SVG_DocumentRec)


class RecordingSurface(SVGSurface):
    def __init__(self, tree, *args, **kwargs):
        self.tree = tree
        super().__init__(tree, *args, **kwargs)

    def _create_surface(self, width, height):
        _, _, viewbox = cairosvg.surface.node_format(self, self.tree)
        return cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, (0, 0, width, height)), width, height


print("freetype version:", freetype.version())
#print("SVG_Lib_Init_Func: ", freetype.raw._lib.SVG_Lib_Init_Func)


# Initialize Pygame
pygame.init()


def get_svg_content_bounds(svg_node):
    """
    Calculates the bounding box (bounds) of SVG content when no explicit 
    width, height, or viewBox is defined.

    Args:
        svg_node (Tree): The tree node for the svg object to calculate the bounds of

    Returns:
        tuple: A tuple containing the bounds (min_x, min_y, width, height) 
               in user units.
    """
    # 2. Create a dummy Surface object to access the internal calculation logic
    # We don't actually render anything here, just use the helper functions.
    # The Surface class takes optional output dimensions, but we can rely
    # on the internal calculation logic if not provided.
    surface = SVGSurface(svg_node, output=None, output_width=1, output_height=1, scale=1, dpi=96)
    
    # 3. Calculate the bounding box of the entire SVG content
    # This function returns a tuple of (min_x, min_y, width, height)
    dims = 1024
    if svg_node.tag == 'svg':
        for child in svg_node.children:
            if child.tag == 'g':
                glyph_node = child
                break
    else:
        glyph_node = svg_node
    if glyph_node is None:
        return None
    bounds = cairosvg.bounding_box.calculate_bounding_box(surface, glyph_node)
    min_x, min_y, width, height = bounds
    print(f"Calculated Bounds (min_x, min_y, width, height): {bounds}")
    print(f"l: {min_x} r: {dims - (min_x + width)} t: {dims - (-min_y)} b: {min_y + height}")

    return bounds


def load_font(font_path, size):
    """Load a font and return the freetype Face object."""
    # Load the font
    face = freetype.Face(font_path)

    # Get available fixed sizes if any
    if face.available_sizes:
        print("Available fixed sizes:", [size.height for size in face.available_sizes])
        face.set_char_size(int(face.available_sizes[-1].size))
    elif face.is_scalable:
        print(f"Font is scalable. Units per EM: {face.units_per_EM}")
        print(f"Height metrics - Ascender: {face.ascender}, Descender: {face.descender}, height: {face.height}")
        print(f"bbox - min: {face.bbox.xMin, -face.bbox.yMax}, max: {face.bbox.xMax, -face.bbox.yMin}")
        # Set the size (you can use either method)
        # face.set_char_size(size * 64, 0, 72, 72)  # size in points, resolution in DPI
        face.set_pixel_sizes(size, size)  # width and height in pixels
    else:
        print("Font is not scalable and has no available sizes.")
        exit(1)
    print(f"Font has {face.num_glyphs} glyphs")

    return face


def render_glyph(face: freetype.Face):
    glyph : freetype.GlyphSlot = face.glyph
    if glyph is None:
        print(f"Glyph for codepoint not found in font.")
        return None
    glyph_index = glyph._FT_GlyphSlot.contents.glyph_index
    print(f"Glyph format for {glyph_index}: {glyph.format.to_bytes(4, 'big').decode('ascii')}")
    if glyph.format == freetype.FT_GLYPH_FORMAT_BITMAP or glyph.format == freetype.FT_GLYPH_FORMAT_OUTLINE:
        glyph.render(freetype.FT_RENDER_MODE_NORMAL)
        # Render the glyph onto the surface
        bitmap = glyph.bitmap
        # Check bitmap format
        print(f"Bitmap format: {bitmap.pixel_mode}, size: {bitmap.width, bitmap.rows}")
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
        doc_bytes_type = ctypes.POINTER(ctypes.c_ubyte * svg_doc.svg_document_length)
        svg_data = bytes(ctypes.cast(svg_doc.svg_document, doc_bytes_type).contents)
        
        if not svg_data:
            print(f"No SVG data found for glyph {glyph_index}")
            return None
        #with open(f"img{glyph_index}.svg", "wb") as f:
        #    f.write(svg_data)
        print(f"glyph metrics - width: {glyph.metrics.width}, height: {glyph.metrics.height}")
        print(f"glyph metrics - horiBearingX: {glyph.metrics.horiBearingX}, horiBearingY: {glyph.metrics.horiBearingY}, horiAdvance {glyph.metrics.horiAdvance}")
        print('svg_data length:', svg_doc.svg_document_length, 'start_glyph_id:', svg_doc.start_glyph_id, 'end_glyph_id:', svg_doc.end_glyph_id)
        print(f"Height metrics - Ascender: {svg_doc.metrics.ascender}, Descender: {svg_doc.metrics.descender}, height: {svg_doc.metrics.height}")
        print(f"Height metrics - x_ppem:   {svg_doc.metrics.x_ppem},   y_ppem:    {svg_doc.metrics.y_ppem}     uperem: {svg_doc.units_per_EM}")
        print(f"Height metrics - x_scale:  {svg_doc.metrics.x_scale / (1 << 16)},  y_scale:   {svg_doc.metrics.y_scale / (1 << 16)}")
        print(f"transform:  {svg_doc.transform.xx / (1 << 16), svg_doc.transform.xy / (1 << 16)},  {svg_doc.transform.yx / (1 << 16), svg_doc.transform.yy / (1 << 16)}")
        print('Vector:', svg_doc.delta.x, svg_doc.delta.y)
        tree = cairosvg.parser.Tree(bytestring=svg_data)
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
        
        #l, t, w, h = get_svg_content_bounds(tree)
        print(f"bbox - min: {face.bbox.xMin, -face.bbox.yMax}, max: {face.bbox.xMax, -face.bbox.yMin}")
        l, t, w, h = face.bbox.xMin, -face.bbox.yMax, (face.bbox.xMax - face.bbox.xMin), (face.bbox.yMax - face.bbox.yMin)
        tree['viewBox'] = f"{l} {t} {w} {h}"
        tree['overflow'] = 'visible'
        scale = svg_doc.metrics.x_ppem / svg_doc.units_per_EM
        print(l, t, w, h)
        #surface = RecordingSurface(tree, output=None, scale=scale, dpi=96)
        #print('extents', surface.cairo.ink_extents())
        #svg_data = svg_data.replace('"1.1"', f'"1.1" viewBox="{face.bbox.xMin} {-face.bbox.yMax} {face.bbox.xMax - face.bbox.xMin} {face.bbox.yMax - face.bbox.yMin}"')
        # if 'viewBox' not in tree:
        #     tree['viewBox'] = f"{l} {t} {w} {h}"

        # transform = np.matrix([
        #     (svg_doc.transform.xx / (1 << 16), svg_doc.transform.xy / (1 << 16)),
        #     (svg_doc.transform.yx / (1 << 16), svg_doc.transform.yy / (1 << 16)),
        #     (svg_doc.delta.x / 64 * svg_doc.units_per_EM / svg_doc.metrics.x_ppem, svg_doc.delta.y / 64 * svg_doc.units_per_EM / svg_doc.metrics.y_ppem),
        # ])
        # m_scale = np.matrix([
        #     (svg_doc.metrics.x_ppem / svg_doc.units_per_EM, 0, 0), 
        #     (svg_doc.metrics.y_ppem / svg_doc.units_per_EM, 0, 0),
        # ])
        # matrix = transform * m_scale
        # extents = [
        #     (l, t),
        #     (l + w, t),
        #     (l + w, t + h),
        #     (l, t + h),
        # ]
        # for i, (x, y) in enumerate(extents):
        #     nx = x * matrix[0][0] + y * matrix[1][0] + matrix[2][0]
        #     ny = x * matrix[0][1] + y * matrix[1][1] + matrix[2][1]
        #     extents[i] = (nx, ny)
        
        #svg_data = svg_data.replace(b'"1.1"', f'"1.1" viewBox="{l} {t} {w} {h}"'.encode())
        scale = svg_doc.metrics.x_ppem / svg_doc.units_per_EM
        #glyph._FT_GlyphSlot.contents.bitmap_left = int(l * scale)
        #glyph._FT_GlyphSlot.contents.bitmap_top = -int(t * scale)
        glyph._FT_GlyphSlot.contents.bitmap_top = face.size.y_ppem

        try:
            # Render SVG to PNG bytes at requested pixel size (width x height)
            #png_surface = PNGSurface(tree, io.BytesIO(), output_width=face.size.x_ppem, output_height=face.size.y_ppem, scale=scale, dpi=96)
            png_surface = PNGSurface(tree, io.BytesIO(), scale=scale, dpi=96)
            png_surface.finish()
            png_bytes = png_surface.output.getvalue()
            #cairo.surfaces.ImageSurface()
        except Exception as e:
            print("Failed to rasterize SVG glyph:", e)
            return None
        img = pygame.image.load(io.BytesIO(png_bytes))  # .convert_alpha()
        print(f"Rasterized SVG glyph size: {len(png_bytes)} bytes, dims {img.get_width(), img.get_height()}")
        # Ensure it fits the target surface size (scale if needed) and blit
        #if (img.get_width(), img.get_height()) != (surface.get_width(), surface.get_height()):
        #    img = pygame.transform.smoothscale(img, (surface.get_width(), surface.get_height()))
        return img
    else:
        print(f"Glyph format is not bitmap for codepoint {glyph_index}: {glyph.format.to_bytes(4, 'big').decode('ascii')}")
        return None
    

# Example usage:
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font_path = "./pygame/fonts/NotoColorEmoji-Regular.ttf"
#font_path = "./pygame/AppleColorEmoji.ttf"

#emoji_codepoint = 0x1F600  # U+1F600 (grinning face)
size = 64
pygame.display.set_mode((256, 256))
pygame.display.set_caption("Emoji Test")
screen = pygame.display.get_surface()
face = load_font(font_path, size)
size = face.size.x_ppem
left = screen.get_width()//2 - size//2
top = screen.get_height()//2 - size//2
print('size', (face.size.x_ppem, face.size.y_ppem))


def update_screen():
    surface = render_glyph(face)
    screen.fill((128, 128, 128, 255))
    screen.fill((0, 0, 0, 255), (left, top, size, size))
    if surface is not None:
        surface = surface.convert_alpha()
        print('offset:', face.glyph.bitmap_left, face.glyph.bitmap_top)
        screen.blit(surface, (left + face.glyph.bitmap_left, top + size - face.glyph.bitmap_top))
    pygame.display.flip()


def glyph_scroll():
    dir_keys = [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_d, pygame.K_a, pygame.K_w, pygame.K_s, pygame.K_UP, pygame.K_DOWN]
    code_point = 0
    while True:
        face.load_glyph(code_point, freetype.FT_LOAD_COLOR)
        update_screen()
        running = True
        while running:
            time.sleep(0.1)
            keys = set()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit()
                elif event.type == pygame.KEYDOWN:
                    keys.add(event.key)
            pressed = pygame.key.get_pressed()
            for key in dir_keys:
                if pressed[key]:
                    keys.add(key)
            if pygame.K_RIGHT in keys or pygame.K_d in keys:
                code_point += 1
            elif pygame.K_LEFT in keys or pygame.K_a in keys:
                code_point -= 1
            elif pygame.K_UP in keys or pygame.K_w in keys:
                code_point += 100
            elif pygame.K_DOWN in keys or pygame.K_s in keys:
                code_point -= 100
            else:
                continue
            if code_point < 0:
                code_point = 0
            elif code_point >= face.num_glyphs:
                code_point = face.num_glyphs - 1
            break

    pygame.quit()
    exit()


def show_emoji():
    # 3391: hot dog
    for emoji in [0x1F600, '🍎', '🍒', '🍊', '🍓', '🍇', '🍑', ]:
        if isinstance(emoji, str):
            emoji_codepoint = ord(emoji)
        else:
            emoji_codepoint = emoji
        print(emoji, '=', hex(emoji_codepoint))
        face.load_char(emoji_codepoint, freetype.FT_LOAD_COLOR)
        update_screen()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit()
                elif event.type == pygame.KEYDOWN and event.key in {pygame.K_RETURN, pygame.K_KP_ENTER}:
                    running = False
                    break
            pygame.display.flip()
            
    pygame.quit()
    exit()

glyph_scroll()
show_emoji()
