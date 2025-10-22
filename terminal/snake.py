#!/usr/bin/env -S - python3
import shutil
import sys
import tty
import termios
import atexit
import time
import select
import random
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
    
    def __str__(self):
        return str(self.tuple())

    def __eq__(self, value):
        return self.tuple() == value.tuple()

    def __hash__(self):
        return hash(self.tuple())


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
    def __init__(self, glyph_width=1):
        width, height = shutil.get_terminal_size()
        width = width // glyph_width
        super().__init__(width, height)
        self.glyph_width = glyph_width
    
    def draw_glyph(self, pos, glyph):
        alignment = len(glyph) % self.glyph_width
        if alignment != 0:
            glyph += ' ' * (self.glyph_width - alignment)
        move_cursor(pos.x * self.glyph_width, pos.y)
        print(glyph, end='')
        for grid_idx, glyph_idx in enumerate(range(0, len(glyph), self.glyph_width)):
            cur = glyph[glyph_idx:glyph_idx + self.glyph_width]
            self[pos.x + grid_idx, pos.y] = cur

    def draw_border(self, start=Point(0, 0), end=None, border='█', clear=True, h_size=1, v_size=1):
        if len(border) == 1:
            border = border * self.glyph_width
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
                    fill = ' ' * self.glyph_width
                else:
                    continue
                self.draw_glyph(Point(x, y), fill)

    def dialog(self, message):
        mid_x = self.width // 2
        mid_y = self.height // 2
        msg_glyph_len = (len(message) + self.glyph_width - 1) // self.glyph_width
        start_x = mid_x - msg_glyph_len // 2
        self.draw_border(start=Point(start_x - 3, mid_y - 2), end=Point(start_x + msg_glyph_len + 2, mid_y + 2), border='#')
        self.draw_glyph(Point(start_x, mid_y), message)
        sys.stdout.flush()

#U_HEAD = ' ^'
#D_HEAD = ' v'
#L_HEAD = ' <'
#R_HEAD = '─>'

#U_HEAD = ' △'
#D_HEAD = ' ▽'
#L_HEAD = ' ◁'
#R_HEAD = '─▷'

U_HEAD = ' ▲'
D_HEAD = ' ▼'
L_HEAD = ' ◄'
R_HEAD = '─►'

# The fruit are wider than a single monospaced character, so put them on the left side
TREATS = [ '🍎 ', '🍒 ', '🍊 ', '🍓 ', '🍇 ', '🍑 ' ]
#          '1234'
BLANK = '  '
KEY_MAP = {
    'w': U_HEAD,
    'a': L_HEAD,
    's': D_HEAD,
    'd': R_HEAD,
}
DIR_MAP = {
    U_HEAD: Point(0, -1),
    D_HEAD: Point(0, 1),
    L_HEAD: Point(-1, 0),
    R_HEAD: Point(1, 0),
}
REVERSE_MAP = {
    U_HEAD: D_HEAD,
    D_HEAD: U_HEAD,
    L_HEAD: R_HEAD,
    R_HEAD: L_HEAD,
}
TURN_MAP = {
    U_HEAD: { R_HEAD: ' ╭', L_HEAD: '─╮', U_HEAD: ' │' },
    D_HEAD: { R_HEAD: ' ╰', L_HEAD: '─╯', D_HEAD: ' │' },
    L_HEAD: { U_HEAD: ' ╰', D_HEAD: ' ╭', L_HEAD: '──' },
    R_HEAD: { U_HEAD: '─╯', D_HEAD: '─╮', R_HEAD: '──' },
}
CRASH_MAP = {
    U_HEAD: ' ☠︎',
    D_HEAD: ' ☠︎',
    L_HEAD: ' ☠︎',
    R_HEAD: '─☠︎',
}


def invert_color(text):
    return f'\033[7m{text}\033[0m'


STARTING_INTERVAL = 0.8
BASE_LENGTH = 2


def print_score(screen, score, speed):
    width = (screen.width - 2) * screen.glyph_width
    left_msg = f'Score: {score}'
    right_msg = f'Speed: {speed:.2f}s'
    mid_space = width - len(left_msg) - len(right_msg)
    msg = left_msg + ' ' * mid_space + right_msg
    move_cursor(screen.glyph_width, 0)
    print(invert_color(msg), end='')


def run():
    screen = Screen(glyph_width=2)
    if screen.width > screen.height * 2:
        screen.width = screen.height * 2
    screen.draw_border()
    pos = Point(1, 1)
    cur_dir = R_HEAD
    interval = STARTING_INTERVAL
    length = BASE_LENGTH
    body = deque([pos])
    treats = set()
    treat_counter = 20
    print_score(screen, 0, interval)
    while True:
        screen.draw_glyph(pos, cur_dir)
        # Handle Treats
        treat_counter -= 1
        if treat_counter == 0 and len(treats) < 3:
            while True:
                treat_pos = Point(random.randint(1, screen.width - 2), random.randint(1, screen.height - 2))
                if screen[treat_pos] == BLANK:
                    break
            screen.draw_glyph(treat_pos, random.choice(TREATS))
            treats.add(treat_pos)
            treat_counter = random.randint(10, 20)  # Number of moves before next treat
        elif treat_counter < 0 or (len(treats) == 0 and treat_counter > 5):
            treat_counter = random.randint(1, 5)

        sys.stdout.flush()
        now = time.time()
        stop = now + interval
        prev_dir = cur_dir
        while now < stop:
            rlist, _, _ =  select.select([sys.stdin], [], [], stop - now)
            if sys.stdin in rlist:
                c = sys.stdin.read(1).lower()
                new_dir = KEY_MAP.get(c, cur_dir)
                # Prevent reversing direction
                if REVERSE_MAP[new_dir] != prev_dir:
                    cur_dir = new_dir
            now = time.time()
        pos += DIR_MAP[cur_dir]
        # Check for treat
        if pos in treats:
            treats.remove(pos)
            length += 1
            interval = max(0.1, interval * 0.90)  # Speed up
            screen.draw_glyph(pos, BLANK)
            print_score(screen, length - BASE_LENGTH, interval)
        # Remove tail if necessary, before checking collisions
        if len(body) >= length:
            tail_pos = body.popleft()
            screen.draw_glyph(tail_pos, BLANK)
        screen.draw_glyph(body[-1], TURN_MAP[screen[body[-1]]][cur_dir])
        if screen[pos] != BLANK:
            crash_char = screen[pos]
            # Hit border or body, game over
            screen.draw_glyph(pos, CRASH_MAP[cur_dir])
            screen.dialog(f"Game Over! Press Enter to exit.")
            input()
            break
        body.append(pos)


if __name__ == '__main__':
    try:
        prepare_terminal()
        run()
    finally:
        atexit._run_exitfuncs()
        atexit._clear()
