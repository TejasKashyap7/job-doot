"""Human-like input: ghost-cursor mouse paths, wheel scrolling, typing with rhythm."""
import random
import time

from ._bezier_shim import install as _install_bezier_shim

_install_bezier_shim()  # must run before ghost-cursor imports `bezier`
from python_ghost_cursor.playwright_sync import create_cursor  # noqa: E402


def pause(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))


class Human:
    def __init__(self, page):
        self.page = page
        vw, vh = self._viewport()
        self.cursor = create_cursor(page, {"x": random.uniform(0.3, 0.7) * vw,
                                           "y": random.uniform(0.3, 0.7) * vh})

    def _viewport(self):
        size = self.page.evaluate("({w: innerWidth, h: innerHeight})")
        return size["w"], size["h"]

    # ---- scrolling ----
    def wheel(self, dy: float) -> None:
        sign = 1 if dy > 0 else -1
        moved = 0
        while abs(moved) < abs(dy):
            step = random.randint(60, 140) * sign
            self.page.mouse.wheel(0, step)
            moved += step
            time.sleep(random.uniform(0.04, 0.16))

    def bring_into_view(self, el) -> None:
        for _ in range(12):
            box = el.bounding_box()
            if box is None:
                break
            _, vh = self._viewport()
            if box["y"] >= 70 and box["y"] + box["height"] <= vh - 50:
                return
            self.wheel(box["y"] - vh * random.uniform(0.3, 0.5))
            pause(0.2, 0.5)
        el.scroll_into_view_if_needed()

    def read_page(self, seconds_range=(8, 30)) -> None:
        """Skim a page: a few scrolls down with pauses, then back towards the top."""
        end = time.time() + random.uniform(*seconds_range)
        total = 0
        while time.time() < end:
            d = random.randint(250, 700)
            self.wheel(d)
            total += d
            pause(1.5, 5.0)
        self.wheel(-total * random.uniform(0.9, 1.1))
        pause(0.5, 1.5)

    # ---- mouse ----
    def hover(self, el) -> None:
        self.bring_into_view(el)
        self.cursor.move(el)
        pause(0.2, 0.7)

    def click(self, el) -> None:
        self.bring_into_view(el)
        pause(0.4, 1.6)  # think before clicking
        self.cursor.click(el, wait_for_click=random.randint(50, 140))

    # ---- keyboard ----
    def type(self, el, text: str) -> None:
        self.click(el)
        if el.input_value():
            self.page.keyboard.press("Control+A")
            pause(0.1, 0.3)
            self.page.keyboard.press("Backspace")
            pause(0.2, 0.5)
        for ch in str(text):
            self.page.keyboard.type(ch)
            time.sleep(random.uniform(0.06, 0.22))
            if random.random() < 0.04:
                pause(0.3, 1.0)
        pause(0.3, 0.9)
