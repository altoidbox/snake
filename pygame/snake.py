#!/usr/bin/env python3
import pygame
import random
import sys
import time
import os
from collections import deque
from dataclasses import dataclass
import freetype
import numpy as np
import font


FILE_DIR = os.path.dirname(os.path.abspath(__file__))
# Add some newer enum values to freetype
freetype.FT_PIXEL_MODE_BGRA = 7
freetype.FT_LOAD_NO_SVG = (1 << 24)
freetype.FT_GLYPH_FORMAT_SVG = int.from_bytes('SVG '.encode('ascii'))

pygame.init()

# Configuration
CELL = 60
SCORE_BAR_HEIGHT = CELL / 2
GRID_W = 15
GRID_H = 12
WINDOW_W = GRID_W * CELL
WINDOW_H = GRID_H * CELL + SCORE_BAR_HEIGHT  # extra for score bar
FPS = 60

MOVES_PER_SECOND = 1.25
SPEED_INCREASE = 0.25
MAX_MOVES_PER_SECOND = 9

STARTING_INTERVAL = 0.8
MINIMUM_INTERVAL = 0.1
INTERVAL_ADJUSTMENT = 0.94  # each treat reduces interval by this factor

BASE_LENGTH = 2

# Colors
BG = (10, 10, 10)  # Dark background
GRID_COLOR = (30, 30, 30)  # Dark gray
BORDER_COLOR = (70, 70, 70)  # Light gray
SNAKE_COLOR = (50, 220, 50)  # Green
HEAD_COLOR = (20, 200, 20)  # Darker Green
# Treat colors, first is red, second orange, third yellow, fourth purple
TREAT_COLORS = [(220, 60, 60), (220, 140, 40), (220, 200, 40), (200, 80, 180)]
TREAT_ICONS =  ['🍎', '🍒', '🍊', '🍓', '🍇', '🍑']
TEXT_COLOR = (230, 230, 230)  # Off-white
DIALOG_BG = (40, 40, 40)  # Dark gray for dialog background
FULL_TRANSPARENCY = (0, 0, 0, 0)

HEAD_SCALE = 2.0
BODY_SCALE = 1.0


def transform_pan(surface: pygame.Surface, offset_dims: tuple[int, int]) -> pygame.Surface:
    """Pan the surface by offset_dims (x, y)"""
    new_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    new_surface.blit(surface, offset_dims)
    return new_surface


class Image:
    _all = {}

    def __init__(self, name: str, surface: pygame.Surface):
        self.name = name
        self.surface = surface
        Image._all[name] = surface

    @classmethod
    def get(cls, key):
        return cls._all[key]


class FileImage(Image):
    def __init__(self, name: str, scale: float, backup_color):
        path = os.path.join(FILE_DIR, 'images', f'{name}.png')
        size = (CELL * scale, CELL * scale)
        if os.path.exists(path):
            surface = pygame.image.load(path)
            surface = pygame.transform.smoothscale(surface, size)
        else:
            # Create placeholder image
            surface = pygame.Surface(size)
            surface.fill(backup_color)
        super().__init__(name, surface)
    

class HeadImage(FileImage):
    def __init__(self, name: str, scale: float = HEAD_SCALE):
        super().__init__(name, scale, HEAD_COLOR)


class BodyImage(FileImage):
    def __init__(self, name: str, scale: float = BODY_SCALE):
        super().__init__(name, scale, SNAKE_COLOR)


class GlyphImage(Image):
    def __init__(self, name: str, glyph: str, scale: float = 1.0):
        #font_name = os.path.join(FILE_DIR, 'fonts', 'AppleColorEmoji.ttf')
        font_name = os.path.join(FILE_DIR, 'fonts', 'NotoColorEmoji-Regular.ttf')
        face = font.load_font(font_name, int(CELL * scale))
        surface = font.render_glyph(face, char=glyph)
        if surface is None:
            exit(1)
        #width, height = surface.get_size()
        #scale_factor = min(CELL * scale / width, CELL * scale / height)
        #surface = pygame.transform.smoothscale(surface, (int(width * scale_factor), int(height * scale_factor)))
        # surface = pygame.font.Font(os.path.join(FILE_DIR, 'NotoColorEmoji-Regular.ttf'), size).render(glyph, True, TEXT_COLOR)
        super().__init__(name, surface)


# Images
FOOD_HEADS_PROB = [0.7, 0.2, 0.1]  # probabilities for food headsq
FOOD_HEADS = [img.surface for img in (HeadImage('happy'), HeadImage('surprised'), HeadImage('bleh'))]
DEAD_HEADS = [img.surface for img in (HeadImage('angry'), HeadImage('sad'), HeadImage('airplane'))]
OTHER_PARTS = [img.surface for img in (HeadImage('head'), BodyImage('body'), BodyImage('turn'), BodyImage('tail'))]
TREATS = [img.surface for img in (GlyphImage(f'treat_{i}', glyph, 0.75) for i, glyph in enumerate(TREAT_ICONS))]

DEFAULT_HEAD = Image.get('head')
DEFAULT_BODY = Image.get('body')
DEFAULT_TURN = Image.get('turn')
DEFAULT_TAIL = Image.get('tail')

@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __add__(self, other: 'Point') -> 'Point':
        return Point(self.x + other.x, self.y + other.y)


# Direction points
UP = Point(0, -1)
DOWN = Point(0, 1)
LEFT = Point(-1, 0)
RIGHT = Point(1, 0)

# Can use wasd or arrow keys
KEY_MAP = {
    pygame.K_w: UP,
    pygame.K_UP: UP,
    pygame.K_s: DOWN,
    pygame.K_DOWN: DOWN,
    pygame.K_a: LEFT,
    pygame.K_LEFT: LEFT,
    pygame.K_d: RIGHT,
    pygame.K_RIGHT: RIGHT,
}


def in_bounds(p: Point) -> bool:
    return 1 <= p.x < GRID_W - 1 and 1 <= p.y < GRID_H - 1


def draw_cell(surface: pygame.Surface, pos: Point, color: tuple[int, int, int]):
    rect = pygame.Rect(pos.x * CELL, pos.y * CELL + SCORE_BAR_HEIGHT, CELL, CELL)
    pygame.draw.rect(surface, color, rect)


def spawn_treat(snake: 'Snake', treats: dict):
    while True:
        p = Point(random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
        if p not in snake and p not in treats:
            return p


def dialog(surface: pygame.Surface, font: pygame.font.Font, text: str):
    txt = [font.render(line, True, TEXT_COLOR) for line in text.splitlines()]
    total_width = max(t.get_width() for t in txt) + CELL * 2
    total_height = sum((t.get_height() * 1.2) for t in txt) + CELL
    s = pygame.Surface((total_width, total_height))
    s.fill(DIALOG_BG)
    pygame.draw.rect(s, TEXT_COLOR, s.get_rect(), 2)
    line_y = CELL // 2
    for i, line in enumerate(txt):
        line_padding = line.get_height() * 0.1
        line_y += line_padding
        s.blit(line, (total_width // 2 - (line.get_width() // 2), line_y))
        line_y += line.get_height() + line_padding
    surface.blit(s, ((WINDOW_W - s.get_width()) // 2, (WINDOW_H - s.get_height()) // 2))
    pygame.display.flip()


TURN_TABLE = {
    (UP, LEFT): lambda img: pygame.transform.flip(img, True, False),
    (UP, RIGHT): lambda img: img,
    (DOWN, LEFT): lambda img: pygame.transform.flip(img, True, True),
    (DOWN, RIGHT): lambda img: pygame.transform.flip(img, False, True),
    (LEFT, UP): lambda img: pygame.transform.rotate(img, 90),
    (LEFT, DOWN): lambda img: pygame.transform.flip(pygame.transform.rotate(img, 90), False, True),
    (RIGHT, UP): lambda img: pygame.transform.flip(pygame.transform.rotate(img, -90), False, True),
    (RIGHT, DOWN): lambda img: pygame.transform.rotate(img, -90),
}

ROTATE_TABLE = {
    UP: lambda img: img,
    DOWN: lambda img: pygame.transform.rotate(img, 180),
    LEFT: lambda img: pygame.transform.rotate(img, 90),
    RIGHT: lambda img: pygame.transform.rotate(img, -90),
}
# For the body, left and right are the same
BODY_ROTATE_TABLE = dict(ROTATE_TABLE)
BODY_ROTATE_TABLE[LEFT] = BODY_ROTATE_TABLE[RIGHT]


class Snake(object):
    def __init__(self, position: Point, direction=RIGHT, length=BASE_LENGTH):
        self.body = deque()
        self.head = position
        self.body_set = {position}
        self.direction = direction
        self.next_direction = direction
        self.length = length

    def move(self):
        if self.direction != self.next_direction:
            # Add a turn segment
            image = TURN_TABLE[(self.direction, self.next_direction)](DEFAULT_TURN)
        else:
            image = BODY_ROTATE_TABLE[self.direction](DEFAULT_BODY)
        self.body.appendleft((self.head, image, self.next_direction))
        self.direction = self.next_direction
        self.head += self.direction
        # Remove the tail before checking collisions
        while len(self.body) > self.length:
            tail, _, _ = self.body.pop()
            self.body_set.remove(tail)
        collision = not in_bounds(self.head) or self.head in self.body_set
        self.body_set.add(self.head)
        if collision:
            raise ValueError("Head position out of bounds or collides with body")

    def __contains__(self, item):
        return item in self.body_set

    def __len__(self):
        return len(self.body_set)


class Game(object):
    def __init__(self, debug=False):
        self.debug = debug
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Cat Creature Snake Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, CELL)

        # Initialize game state
        self.reset()

    def reset(self):
        # Initialize game state
        self.moves_per_second = MOVES_PER_SECOND
        self.interval = 1 / self.moves_per_second  # STARTING_INTERVAL
        self.snake = Snake(Point(2, 2), direction=RIGHT, length=BASE_LENGTH)
        self.treats = {}
        self.treat_counter = 20
        self.score = 0

        self.last_move = time.time()
        self.running = True
        self.game_over = False

        self.head_image = DEFAULT_HEAD
        self.draw()


    def run(self):
        head_image_time = time.time()
        while self.running:
            now = time.time()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    nd = KEY_MAP.get(event.key)
                    if nd:
                        # prevent reverse
                        if len(self.snake) < 2 or self.snake.head + nd != self.snake.body[0][0]:
                            self.snake.next_direction = nd

            # Move on interval
            if now - self.last_move >= self.interval:
                if now - head_image_time > 0.9:
                    self.head_image = DEFAULT_HEAD
                self.last_move = now
                try:
                    self.snake.move()
                except ValueError:
                    self.head_image = random.choice(DEAD_HEADS)
                    self.game_over = True
                else:
                    # Treat logic
                    if self.snake.head in self.treats:
                        self.head_image = random.choices(FOOD_HEADS, FOOD_HEADS_PROB)[0]
                        head_image_time = time.time()
                        self.treats.pop(self.snake.head)
                        self.snake.length += 1
                        self.score += 1
                        self.moves_per_second += SPEED_INCREASE
                        if self.moves_per_second > MAX_MOVES_PER_SECOND:
                            self.moves_per_second = MAX_MOVES_PER_SECOND
                        self.interval = 1 / self.moves_per_second
                        #self.interval = max(MINIMUM_INTERVAL, self.interval * INTERVAL_ADJUSTMENT)

                    self.treat_counter -= 1
                    if self.treat_counter <= 0 and len(self.treats) < 3:
                        self.treats[spawn_treat(self.snake, self.treats)] = random.choice(TREATS)  # TREAT_COLORS
                        self.treat_counter = random.randint(10, 20)
                    elif self.treat_counter < 0 or (len(self.treats) == 0 and self.treat_counter > 5):
                        self.treat_counter = random.randint(1, 5)

            self.clock.tick(FPS)
            self.draw()

            # If game over, show dialog and wait for key
            if self.game_over:
                dialog(self.screen, self.font, "Game Over!\nContinue? (Y/N/Q)")
                # freeze until user presses esc/q/n or closes, can continue with y/enter
                while True:
                    ev = pygame.event.wait()
                    if ev.type == pygame.QUIT:
                        self.running = False
                        break
                    elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_n):
                        self.running = False
                        break
                    elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_y, pygame.K_KP_ENTER):
                        self.reset()
                        break

        pygame.quit()
        sys.exit()
    
    def draw_cell(self, surface: pygame.Surface, pos: Point):
        self.screen.blit(surface, 
            (pos.x * CELL - (surface.get_width() - CELL) // 2, 
            pos.y * CELL + SCORE_BAR_HEIGHT - (surface.get_height() - CELL) // 2))


    def draw(self):
        self.screen.fill(BG)

        # draw border area background
        pygame.draw.rect(self.screen, GRID_COLOR, (0, SCORE_BAR_HEIGHT, WINDOW_W, WINDOW_H - SCORE_BAR_HEIGHT))
        # border
        for x in range(GRID_W):
            draw_cell(self.screen, Point(x, 0), BORDER_COLOR)
            draw_cell(self.screen, Point(x, GRID_H - 1), BORDER_COLOR)
        for y in range(GRID_H):
            draw_cell(self.screen, Point(0, y), BORDER_COLOR)
            draw_cell(self.screen, Point(GRID_W - 1, y), BORDER_COLOR)

        # score bar
        pygame.draw.rect(self.screen, BORDER_COLOR, (0, 0, WINDOW_W, SCORE_BAR_HEIGHT))
        left_txt = self.font.render(f"Score: {self.score}", True, TEXT_COLOR)
        self.screen.blit(left_txt, (CELL + CELL//10, (CELL + SCORE_BAR_HEIGHT - left_txt.get_height()) // 2))
        right_txt = self.font.render(f"Speed: {self.interval:.2f}s", True, TEXT_COLOR)
        self.screen.blit(right_txt, (WINDOW_W - CELL - (CELL//10) - right_txt.get_width(), (CELL + SCORE_BAR_HEIGHT - right_txt.get_height()) // 2))

        # treats
        for pos, treat in self.treats.items():
            # draw a circle centered in the cell
            # cx = pos.x * CELL + CELL // 2
            # cy = pos.y * CELL + SCORE_BAR_HEIGHT + CELL // 2
            # pygame.draw.circle(self.screen, treat, (cx, cy), CELL // 2 - 2)
            self.draw_cell(treat, pos)

        # snake body (does not include head)
        for pos, image, direction in self.snake.body:
            #draw_cell(self.screen, pos, SNAKE_COLOR)
            if pos == self.snake.body[-1][0]:
                image = ROTATE_TABLE[direction](Image.get('tail'))
            self.draw_cell(image, pos)

        # Some head are smaller, so draw a cropped segment of the body behind the head
        head_bg = DEFAULT_BODY.copy()
        head_bg_rect = head_bg.get_rect()
        pygame.draw.rect(head_bg, FULL_TRANSPARENCY, head_bg_rect.move(0, -head_bg_rect.height // 5))
        head_bg = ROTATE_TABLE[self.snake.direction](head_bg)
        
        # Draw head at position
        self.draw_cell(head_bg, self.snake.head)
        self.draw_cell(self.head_image, self.snake.head)

        pygame.display.flip()


def main():
    debug = len(sys.argv) > 1
    if debug:
        global STARTING_INTERVAL, BASE_LENGTH, MINIMUM_INTERVAL
        STARTING_INTERVAL = 0.5
        MINIMUM_INTERVAL = 0.2
        BASE_LENGTH = 20
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
