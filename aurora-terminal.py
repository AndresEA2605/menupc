#!/usr/bin/env python3
"""Full-screen animated aurora for a terminal tile."""

import curses
import math
import random
import sys


PALETTE = (
    curses.COLOR_CYAN,
    curses.COLOR_GREEN,
    curses.COLOR_BLUE,
    curses.COLOR_MAGENTA,
    curses.COLOR_YELLOW,
    curses.COLOR_WHITE,
)


def animate(screen):
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    color_pairs = [curses.A_NORMAL] * len(PALETTE)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK
        for index, color in enumerate(PALETTE, 1):
            curses.init_pair(index, color, background)
            color_pairs[index - 1] = curses.color_pair(index)

    screen.timeout(40)
    if "--stars" in sys.argv[1:]:
        animate_stars(screen, color_pairs)
        return

    phase = 0.0
    while True:
        height, width = screen.getmaxyx()
        screen.erase()
        for y in range(height):
            vertical = y / max(1, height - 1)
            for x in range(width):
                horizontal = x / max(1, width - 1)
                wave = math.sin(
                    horizontal * math.tau * 1.5
                    + phase
                    + math.sin(vertical * math.tau + phase * 0.7) * 1.3
                )
                depth = math.sin(vertical * math.tau * 1.6 - phase * 0.8 + horizontal * 3.8)
                energy = (wave + depth + 2) / 4
                if energy < 0.34:
                    continue

                character = "." if energy < 0.48 else ":" if energy < 0.62 else "*" if energy < 0.76 else "#"
                color_index = int((horizontal * 2 + vertical + phase * 0.16) * len(PALETTE))
                attribute = color_pairs[color_index % len(PALETTE)]
                if energy >= 0.76:
                    attribute |= curses.A_BOLD
                try:
                    screen.addch(y, x, character, attribute)
                except curses.error:
                    if y != height - 1 or x != width - 1:
                        raise

        screen.refresh()
        if screen.getch() in (ord("q"), ord("Q")):
            break
        phase += 0.055


def animate_stars(screen, color_pairs):
    randomizer = random.Random()
    stars = []
    screen.timeout(40)

    while True:
        height, width = screen.getmaxyx()
        star_count = max(12, min(180, width * height // 8))
        while len(stars) < star_count:
            stars.append([
                randomizer.uniform(0, math.tau),
                randomizer.uniform(0, max(width, height)),
                randomizer.uniform(0.12, 0.38),
                randomizer.randrange(len(color_pairs)),
            ])
        del stars[star_count:]

        screen.erase()
        center_x = (width - 1) / 2
        center_y = (height - 1) / 2
        for star in stars:
            angle, distance, speed, color_index = star
            distance += speed
            star[1] = distance
            x = round(center_x + math.cos(angle) * distance)
            y = round(center_y + math.sin(angle) * distance * 0.5)
            if not (0 <= x < width and 0 <= y < height):
                star[0] = randomizer.uniform(0, math.tau)
                star[1] = 0
                continue

            character = "." if distance < 3 else "+" if distance < 7 else "*" if distance < 12 else "O"
            attribute = color_pairs[color_index]
            if distance >= 7:
                attribute |= curses.A_BOLD
            try:
                screen.addch(y, x, character, attribute)
            except curses.error:
                if y != height - 1 or x != width - 1:
                    raise

        screen.refresh()
        if screen.getch() in (ord("q"), ord("Q")):
            break


if __name__ == "__main__":
    curses.wrapper(animate)