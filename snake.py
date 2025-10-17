#!/usr/bin/env -S - python3
import shutil
import sys
import tty
import termios
import atexit
import time
import select

def move_cursor(x, y):
    """
    Move the cursor to a specific x,y coordinate in the terminal
    """
    print('\033[{};{}H'.format(y, x), end='')


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


stdin = sys.stdin.fileno()
old_settings = termios.tcgetattr(stdin)
screen_contents = save_screen()

atexit.register(lambda: termios.tcsetattr(stdin, termios.TCSANOW, old_settings))
atexit.register(lambda: restore_screen())
atexit.register(lambda: show_cursor())

tty.setcbreak(stdin)
clear_screen()
hide_cursor()

term_width, term_height = shutil.get_terminal_size()
move_cursor(1, 1)
for y in range(1, term_height):
    for x in range(1, term_width):
        move_cursor(x, y)
        if x == 1 or x == term_width - 1:
            print('█', end='')
        elif y == 1 or y == term_height - 1:
            print('█', end='')
        else:
            print(' ', end='')

move_cursor(2, 2)
input("Press Enter to exit...")
