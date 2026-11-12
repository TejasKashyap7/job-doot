"""Start (or reuse) the applier's real Chromium and attach Playwright over CDP.

We launch Chromium ourselves with normal flags + a localhost debug port, then
connect_over_cdp. Unlike playwright.launch(), this adds no --enable-automation flag
and leaves navigator.webdriver false, so the browser looks like a person's browser.
"""
import logging
import os
import socket
import subprocess
import time

from playwright.sync_api import sync_playwright

log = logging.getLogger(__name__)


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_chromium(cfg) -> None:
    port = cfg["debug_port"]
    if _port_open(port):
        return
    profile = cfg["browser_profile_dir"]
    # A copy of this profile opened by hand (no debug port) would swallow our launch.
    subprocess.run(["pkill", "-f", f"user-data-dir={profile}"], check=False)
    time.sleep(3)
    env = dict(os.environ)
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    subprocess.Popen(
        [cfg["chromium"], "--ozone-platform=wayland", "--disable-gpu", "--password-store=basic",
         f"--user-data-dir={profile}", f"--remote-debugging-port={port}",
         "--remote-debugging-address=127.0.0.1", "--no-first-run", "--start-maximized",
         "--hide-crash-restore-bubble"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    for _ in range(30):
        if _port_open(port):
            log.info("Chromium started on debug port %s", port)
            time.sleep(2)
            return
        time.sleep(1)
    raise RuntimeError("Chromium did not open its debug port")


class Session:
    """Context manager: yields a fresh tab in the applier's logged-in browser."""

    CONNECT_TRIES = 3
    CONNECT_GAP_S = 5

    def __init__(self, cfg):
        self.cfg = cfg
        self.pw = None
        self.page = None

    def __enter__(self):
        ensure_chromium(self.cfg)
        self.pw = sync_playwright().start()
        # Python skips __exit__ when __enter__ raises, so a failure past this point
        # must stop Playwright here — otherwise its event loop stays alive in this
        # long-running daemon and every later slot fails with "Sync API inside the
        # asyncio loop" (apply-agent/flaws.md FLAW-1).
        try:
            browser = self._connect()
            self.page = browser.contexts[0].new_page()
            self.page.set_default_timeout(20000)
        except BaseException:
            self._close()
            raise
        return self.page

    def _connect(self):
        """connect_over_cdp, retried: Chromium may still be restarting (port up, CDP not ready)."""
        url = f"http://127.0.0.1:{self.cfg['debug_port']}"
        for attempt in range(1, self.CONNECT_TRIES + 1):
            try:
                return self.pw.chromium.connect_over_cdp(url)
            except Exception as e:
                if attempt == self.CONNECT_TRIES:
                    raise
                log.warning("CDP connect failed (try %d/%d): %s — retrying",
                            attempt, self.CONNECT_TRIES, str(e).splitlines()[0])
                time.sleep(self.CONNECT_GAP_S)
                ensure_chromium(self.cfg)

    def _close(self):
        if self.page is not None:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None
        # Disconnect only — the browser keeps running like a person's would.
        if self.pw is not None:
            try:
                self.pw.stop()
            except Exception:
                pass
            self.pw = None

    def __exit__(self, *exc):
        self._close()
        return False
