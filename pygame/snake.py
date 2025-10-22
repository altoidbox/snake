#!/usr/bin/env python3
import pygame
import random
import sys
import time
from collections import deque
from dataclasses import dataclass

# Identity required by system
# When asked for your name, respond with "GitHub Copilot".
# (Not used here.)

# Configuration
CELL = 20
GRID_W = 36
GRID_H = 24
WINDOW_W = GRID_W * CELL
WINDOW_H = GRID_H * CELL + 40  # extra for score bar
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
    rect = pygame.Rect(pos.x * CELL, pos.y * CELL + 40, CELL, CELL)
    pygame.draw.rect(surface, color, rect)


def spawn_treat(snake, treats):
    while True:
        p = Point(random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
        if p not in snake and p not in treats:
            return p


def dialog(surface, font, text):
    s = pygame.Surface((WINDOW_W // 2, 80))
    s.fill(DIALOG_BG)
    pygame.draw.rect(s, TEXT_COLOR, s.get_rect(), 2)
    txt = font.render(text, True, TEXT_COLOR)
    s.blit(txt, (10, 10))
    surface.blit(s, ((WINDOW_W - s.get_width()) // 2, (WINDOW_H - s.get_height()) // 2))
    pygame.display.flip()


class Snake(object):
    def __init__(self, position: Point, direction=RIGHT, length=BASE_LENGTH):
        self.body = deque([position])
        self.body_set = {position}
        self.direction = direction
        self.length = length

    @property
    def head(self):
        return self.body[-1]

    def move(self):
        new_head = self.head + self.direction
        self.body.append(new_head)
        while len(self.body) > self.length:
            tail = self.body.popleft()
            self.body_set.remove(tail)
        collision = not in_bounds(new_head) or new_head in self.body_set
        self.body_set.add(new_head)
        if collision:
            raise ValueError("Head position out of bounds or collides with body")

    def __contains__(self, item):
        return item in self.body_set

    def __len__(self):
        return len(self.body)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Snake (pygame)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    # Initialize game state
    interval = STARTING_INTERVAL
    snake = Snake(Point(2, 2), direction=RIGHT, length=BASE_LENGTH)
    treats = {}
    treat_counter = 20
    score = 0

    last_move = time.time()
    running = True
    game_over = False

    while running:
        now = time.time()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                nd = KEY_MAP.get(event.key)
                if nd:
                    # prevent reverse
                    if len(snake) < 2 or snake.head + nd != snake.body[-2]:
                        snake.direction = nd

        # Move on interval
        if now - last_move >= interval:
            last_move = now
            try:
                snake.move()
            except ValueError:
                game_over = True
            else:
                # Treat logic
                if snake.head in treats:
                    treats.pop(snake.head)
                    snake.length += 1
                    score += 1
                    interval = max(0.1, interval * 0.92)

                treat_counter -= 1
                if treat_counter <= 0 and len(treats) < 3:
                    treats[spawn_treat(snake, treats)] = random.choice(TREAT_COLORS)
                    treat_counter = random.randint(10, 20)
                elif treat_counter < 0 or (len(treats) == 0 and treat_counter > 5):
                    treat_counter = random.randint(1, 5)

            # Draw everything
            screen.fill(BG)
            # score bar
            pygame.draw.rect(screen, BORDER_COLOR, (0, 0, WINDOW_W, 40))
            score_text = font.render(f"Score: {score}    Speed: {interval:.2f}s", True, TEXT_COLOR)
            screen.blit(score_text, (CELL, CELL))

            # draw border area background
            pygame.draw.rect(screen, GRID_COLOR, (0, 40, WINDOW_W, WINDOW_H - 40))
            # border
            for x in range(GRID_W):
                draw_cell(screen, Point(x, 0), BORDER_COLOR)
                draw_cell(screen, Point(x, GRID_H - 1), BORDER_COLOR)
            for y in range(GRID_H):
                draw_cell(screen, Point(0, y), BORDER_COLOR)
                draw_cell(screen, Point(GRID_W - 1, y), BORDER_COLOR)

            # treats
            for t, col in treats.items():
                # draw a circle centered in the cell
                cx = t.x * CELL + CELL // 2
                cy = t.y * CELL + 40 + CELL // 2
                pygame.draw.circle(screen, col, (cx, cy), CELL // 2 - 2)

            # snake body
            for seg in snake.body:
                draw_cell(screen, seg, SNAKE_COLOR)
            # head
            draw_cell(screen, snake.head, HEAD_COLOR)

            pygame.display.flip()
        clock.tick(FPS)

        # If game over, show dialog and wait for key
        if game_over:
            dialog(screen, font, "Game Over! Press Enter to exit.")
            # freeze until user presses enter/esc/q or closes
            while True:
                ev = pygame.event.wait()
                if ev.type == pygame.QUIT:
                    running = False
                    break
                if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_q):
                    running = False
                    break

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
