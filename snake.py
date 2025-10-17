#!/usr/bin/env -S - python3
import shutil
import sys
import tty
import termios
import atexit
import time
import select
from collections import deque


def move_cursor(x, y):
    """
    Move the cursor to a specific x,y coordinate in the terminal
    Since the terminal coordinates start at 1,1 we add 1 to both x and y
    """
    print('\033[{};{}H'.format(y + 1, x + 1), end='')


def cursor_right(n):
    """
    Move the cursor n spaces to the right
    """
    print('\033[{}C'.format(n), end='')


def save_screen():
    """
    Save the current screen contents
    """
    print('\033[?1049h', end='')


def restore_screen():
    """
    Restore the saved screen contents
    """
    print('\033[?1049l', end='')


def clear_screen():
    """
    Clear the screen
    """
    print('\033[2J', end='')


def hide_cursor():
    """
    Hide the cursor
    """
    print('\033[?25l', end='')


def show_cursor():
    """
    Show the cursor
    """
    print('\033[?25h', end='')


def prepare_terminal():
    """
    Prepare the terminal for raw input
    """
    stdin = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin)
    screen_contents = save_screen()

    atexit.register(lambda: termios.tcsetattr(stdin, termios.TCSANOW, old_settings))
    atexit.register(lambda: restore_screen())
    atexit.register(lambda: show_cursor())

    tty.setcbreak(stdin)
    clear_screen()
    hide_cursor()


class Point(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def tuple(self):
        return (self.x, self.y)


class Grid(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cells = [[' ' for _ in range(width)] for _ in range(height)]
    
    def __getitem__(self, pos):
        if isinstance(pos, Point):
            return self.cells[pos.y][pos.x]
        elif isinstance(pos, tuple):
            x, y = pos
            return self.cells[y][x]
        raise KeyError('Invalid key type')

    def __setitem__(self, pos, value):
        if isinstance(pos, Point):
            self.cells[pos.y][pos.x] = value
        elif isinstance(pos, tuple):
            x, y = pos
            self.cells[y][x] = value
        else:
            raise KeyError('Invalid key type')


class Screen(Grid):
    def __init__(self):
        width, height = shutil.get_terminal_size()
        super().__init__(width, height)
    
    def draw_glyph(self, pos, glyph):
        move_cursor(pos.x, pos.y)
        print(glyph, end='')
        self[pos] = glyph

    def draw_border(self, start=Point(0, 0), end=None, border='█', clear=True, h_size=1, v_size=1):
        if end is None:
            end = Point(self.width - 1, self.height - 1)
        h_border = set(range(start.x, start.x + h_size)) | set(range(end.x - h_size + 1, end.x + 1))
        v_border = set(range(start.y, start.y + v_size)) | set(range(end.y - v_size + 1, end.y + 1))
        move_cursor(0, 0)
        for y in range(start.y, end.y + 1):
            for x in range(start.x, end.x + 1):
                if (x in h_border) or (y in v_border):
                    fill = border
                elif clear:
                    fill = ' '
                else:
                    continue
                self.draw_glyph(Point(x, y), fill)

    def dialog(self, message):
        mid_x = self.width // 2
        mid_y = self.height // 2
        start_x = mid_x - len(message) // 2
        self.draw_border(start=Point(start_x - 3, mid_y - 2), end=Point(start_x + len(message) + 2, mid_y + 2), border='#')
        move_cursor(start_x, mid_y)
        print(message, end='')
        sys.stdout.flush()


DIR_MAP = {
    'w': ('^', Point(0, -1)),
    'a': ('<', Point(-2, 0)),
    's': ('v', Point(0, 1)),
    'd': ('>', Point(2, 0)),
}
TURN_MAP = {
    '^': { '>': '/', '<': '\\', '^': '|' },
    'v': { '>': '\\', '<': '/', 'v': '|' },
    '<': { '^': '\\', 'v': '/', '<': '-' },
    '>': { '^': '/', 'v': '\\', '>': '-' },
}

def run():
    screen = Screen()
    screen.draw_border(h_size=2)
    pos = Point(2, 1)
    cur_dir = DIR_MAP['d']
    interval = 1
    length = 5
    body = deque([pos])
    while True:
        screen.draw_glyph(pos, cur_dir[0])
        sys.stdout.flush()
        now = time.time()
        stop = now + interval
        while now < stop:
            rlist, _, _ =  select.select([sys.stdin], [], [], stop - now)
            if sys.stdin in rlist:
                c = sys.stdin.read(1)
                cur_dir = DIR_MAP.get(c, cur_dir)
            now = time.time()
        _, dp = cur_dir
        pos += dp
        if screen[pos] != ' ':
            # Hit border, game over
            screen.dialog("Game Over! Press Enter to exit.")
            break
        if len(body) >= length:
            tail_pos = body.popleft()
            screen.draw_glyph(tail_pos, ' ')
        screen.draw_glyph(body[-1], TURN_MAP[screen[body[-1]]][cur_dir[0]])
        body.append(pos)


if __name__ == '__main__':
    try:
        prepare_terminal()
        run()
    finally:
        input()
