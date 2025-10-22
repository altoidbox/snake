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
BG = (10, 10, 10)
GRID_COL = (30, 30, 30)
BORDER_COL = (70, 70, 70)
SNAKE_COL = (50, 220, 50)
HEAD_COL = (20, 200, 20)
TREAT_COLS = [(220, 60, 60), (220, 140, 40), (220, 200, 40), (200, 80, 180)]
TEXT_COL = (230, 230, 230)
DIALOG_BG = (40, 40, 40)

# Direction points
@dataclass(frozen=True)
class Point:
    x: int
    y: int

UP = Point(0, -1)
DOWN = Point(0, 1)
LEFT = Point(-1, 0)
RIGHT = Point(1, 0)

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

def add(p: Point, q: Point) -> Point:
    return Point(p.x + q.x, p.y + q.y)

def inside(p: Point) -> bool:
    return 1 <= p.x < GRID_W - 1 and 1 <= p.y < GRID_H - 1

def draw_cell(surface, pos: Point, color):
    rect = pygame.Rect(pos.x * CELL, pos.y * CELL + 40, CELL, CELL)
    pygame.draw.rect(surface, color, rect)

def spawn_treat(snake_set, treats):
    while True:
        p = Point(random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
        if p not in snake_set and p not in treats:
            return p

def dialog(surface, font, text):
    s = pygame.Surface((WINDOW_W // 2, 80))
    s.fill(DIALOG_BG)
    pygame.draw.rect(s, TEXT_COL, s.get_rect(), 2)
    txt = font.render(text, True, TEXT_COL)
    s.blit(txt, (10, 10))
    surface.blit(s, ((WINDOW_W - s.get_width()) // 2, (WINDOW_H - s.get_height()) // 2))
    pygame.display.flip()

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Snake (pygame)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    # Initialize game state
    head = Point(2, 2)
    cur_dir = RIGHT
    interval = STARTING_INTERVAL
    length = BASE_LENGTH
    body = deque([head])
    snake_set = {head}
    treats = set()
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
            elif event.type == pygame.KEYDOWN and not game_over:
                nd = KEY_MAP.get(event.key)
                if nd:
                    # prevent reverse
                    if len(body) < 2 or add(body[-1], nd) != body[-2]:
                        cur_dir = nd
            elif event.type == pygame.KEYDOWN and game_over:
                if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_q):
                    running = False

        # Move on interval
        if not game_over and now - last_move >= interval:
            last_move = now
            head = add(body[-1], cur_dir)

            # Check collisions
            if not inside(head) or head in snake_set:
                game_over = True
            else:
                body.append(head)
                snake_set.add(head)

                # Treat logic
                treat_counter -= 1
                if treat_counter <= 0 and len(treats) < 3:
                    treats.add(spawn_treat(snake_set, treats))
                    treat_counter = random.randint(10, 20)
                elif treat_counter < 0 or (len(treats) == 0 and treat_counter > 5):
                    treat_counter = random.randint(1, 5)

                if head in treats:
                    treats.remove(head)
                    length += 1
                    score = length - BASE_LENGTH
                    interval = max(0.08, interval * 0.90)
                # Remove tail if necessary
                while len(body) > length:
                    tail = body.popleft()
                    snake_set.remove(tail)

        # Draw everything
        screen.fill(BG)
        # score bar
        pygame.draw.rect(screen, BORDER_COL, (0, 0, WINDOW_W, 40))
        score_text = font.render(f"Score: {score}    Speed: {interval:.2f}s", True, TEXT_COL)
        screen.blit(score_text, (8, 8))

        # draw border area background
        pygame.draw.rect(screen, GRID_COL, (0, 40, WINDOW_W, WINDOW_H - 40))
        # border
        for x in range(GRID_W):
            draw_cell(screen, Point(x, 0), BORDER_COL)
            draw_cell(screen, Point(x, GRID_H - 1), BORDER_COL)
        for y in range(GRID_H):
            draw_cell(screen, Point(0, y), BORDER_COL)
            draw_cell(screen, Point(GRID_W - 1, y), BORDER_COL)

        # treats
        for i, t in enumerate(treats):
            col = TREAT_COLS[i % len(TREAT_COLS)]
            # draw a circle centered in the cell
            cx = t.x * CELL + CELL // 2
            cy = t.y * CELL + 40 + CELL // 2
            pygame.draw.circle(screen, col, (cx, cy), CELL // 2 - 2)

        # snake body
        for seg in list(body)[:-1]:
            draw_cell(screen, seg, SNAKE_COL)
        # head
        if body:
            draw_cell(screen, body[-1], HEAD_COL)

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
