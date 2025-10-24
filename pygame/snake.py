#!/usr/bin/env python3
import pygame
import random
import sys
import time
import os
from collections import deque
from dataclasses import dataclass
from itertools import chain


FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
CELL = 60
SCORE_BAR_HEIGHT = CELL / 2
GRID_W = 20
GRID_H = 15
WINDOW_W = GRID_W * CELL
WINDOW_H = GRID_H * CELL + SCORE_BAR_HEIGHT  # extra for score bar
FPS = 60

STARTING_INTERVAL = 0.8
BASE_LENGTH = 2

# Colors
BG = (10, 10, 10)  # Dark background
GRID_COLOR = (30, 30, 30)  # Dark gray
BORDER_COLOR = (70, 70, 70)  # Light gray
SNAKE_COLOR = (50, 220, 50)  # Green
HEAD_COLOR = (20, 200, 20)  # Darker Green
# Treat colors, first is red, second orange, third yellow, fourth purple
TREAT_COLORS = [(220, 60, 60), (220, 140, 40), (220, 200, 40), (200, 80, 180)]
TEXT_COLOR = (230, 230, 230)  # Off-white
DIALOG_BG = (40, 40, 40)  # Dark gray for dialog background

# Images
HEAD_SIZE = int(CELL * 2)
DEFAULT_HEAD = ['head']
FOOD_HEADS = ['surprised', 'happy', 'bleh']
DEAD_HEADS = ['angry', 'sad', 'airplane']
BODY_PARTS = ['body', 'turn']
IMAGES = {}
for name in chain(DEFAULT_HEAD + FOOD_HEADS, DEAD_HEADS, BODY_PARTS):
    path = os.path.join(FILE_DIR, f'{name}.png')
    if os.path.exists(path):
        image = pygame.image.load(path)
        size = (HEAD_SIZE, HEAD_SIZE)
        if name in BODY_PARTS:
            size = (int(CELL * 1.2), int(CELL * 1.2))
        image = pygame.transform.scale(image, size)
    else:
        # Create placeholder image
        if name in BODY_PARTS:
            size = (CELL, CELL)
            color = SNAKE_COLOR
        else:
            size =(int(CELL * 1.2), int(CELL * 1.2))
            color = HEAD_COLOR
        image = pygame.Surface(size)
        image.fill(color)
    IMAGES[name] = image


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __add__(self, other):
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


def draw_cell(surface, pos: Point, color):
    rect = pygame.Rect(pos.x * CELL, pos.y * CELL + SCORE_BAR_HEIGHT, CELL, CELL)
    pygame.draw.rect(surface, color, rect)


def spawn_treat(snake, treats):
    while True:
        p = Point(random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
        if p not in snake and p not in treats:
            return p


def dialog(surface, font, text):
    txt = font.render(text, True, TEXT_COLOR)
    s = pygame.Surface((txt.get_width() + CELL * 2, txt.get_height() + CELL))
    s.fill(DIALOG_BG)
    pygame.draw.rect(s, TEXT_COLOR, s.get_rect(), 2)
    s.blit(txt, (CELL, CELL // 2))
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


def rotate_image(image, direction):
    return ROTATE_TABLE[direction](image)


class Snake(object):
    def __init__(self, position: Point, direction=RIGHT, length=BASE_LENGTH):
        self.body = deque()
        self.head = position
        self.body_set = {position}
        self.direction = direction
        self.next_direction = direction
        self.length = length

    def move(self):
        self.body.appendleft((self.head, self.direction))
        self.direction = self.next_direction
        self.head += self.direction
        # Remove the tail before checking collisions
        while len(self.body) > self.length:
            tail, _ = self.body.pop()
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
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Cat Creature Snake Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, CELL)

        # Initialize game state
        self.interval = STARTING_INTERVAL
        self.snake = Snake(Point(2, 2), direction=RIGHT, length=BASE_LENGTH)
        self.treats = {}
        self.treat_counter = 20
        self.score = 0

        self.last_move = time.time()
        self.running = True
        self.game_over = False

        self.head_image = IMAGES['head']
    
    def run(self):
        self.draw()
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
                    self.head_image = IMAGES['head']
                self.last_move = now
                try:
                    self.snake.move()
                except ValueError:
                    self.head_image = IMAGES[random.choice(DEAD_HEADS)]
                    self.game_over = True
                else:
                    # Treat logic
                    if self.snake.head in self.treats:
                        self.head_image = IMAGES[random.choice(FOOD_HEADS)]
                        head_image_time = time.time()
                        self.treats.pop(self.snake.head)
                        self.snake.length += 1
                        self.score += 1
                        self.interval = max(0.1, self.interval * 0.92)

                    self.treat_counter -= 1
                    if self.treat_counter <= 0 and len(self.treats) < 3:
                        self.treats[spawn_treat(self.snake, self.treats)] = random.choice(TREAT_COLORS)
                        self.treat_counter = random.randint(10, 20)
                    elif self.treat_counter < 0 or (len(self.treats) == 0 and self.treat_counter > 5):
                        self.treat_counter = random.randint(1, 5)

            self.clock.tick(FPS)
            self.draw()

            # If game over, show dialog and wait for key
            if self.game_over:
                dialog(self.screen, self.font, "Game Over! Press Enter to exit.")
                # freeze until user presses enter/esc/q or closes
                while True:
                    ev = pygame.event.wait()
                    if ev.type == pygame.QUIT:
                        self.running = False
                        break
                    if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_q):
                        self.running = False
                        break

        pygame.quit()
        sys.exit()

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
        for t, col in self.treats.items():
            # draw a circle centered in the cell
            cx = t.x * CELL + CELL // 2
            cy = t.y * CELL + SCORE_BAR_HEIGHT + CELL // 2
            pygame.draw.circle(self.screen, col, (cx, cy), CELL // 2 - 2)

        # snake body (does not include head)
        for seg, direction in self.snake.body:
            #draw_cell(self.screen, seg, SNAKE_COLOR)

            image = rotate_image(IMAGES['body'], direction)
            self.screen.blit(image, 
                (seg.x * CELL - (image.get_width() - CELL) // 2, 
                seg.y * CELL + SCORE_BAR_HEIGHT - (image.get_height() - CELL) // 2))
            
        # Rotate image based on direction
        head_image = rotate_image(self.head_image, self.snake.direction)
        # Draw head at position
        self.screen.blit(head_image, 
            (self.snake.head.x * CELL - (head_image.get_width() - CELL) // 2, 
            self.snake.head.y * CELL + SCORE_BAR_HEIGHT - (head_image.get_height() - CELL) // 2))

        pygame.display.flip()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
