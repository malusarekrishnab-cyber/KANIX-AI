"""
router.py — Phase 1

Single source of truth for "are we online or offline right now, and
which provider should each subsystem (main AI / vision / STT) use".

No other file should implement its own internet-check — everyone
calls Router.get() and reads .is_online / .main_ai / .vision / .stt
from the returned RouteState.

Design notes:
- Internet check hits a small, reliable, low-payload endpoint
  (Google's generate_204) with a short timeout. If it hangs or errors
  for ANY reason, we treat that as offline — fail-safe, never hang
  the caller.
- Result is cached for POLL_INTERVAL seconds so we don't do a network
  check on every single AI call. Call Router.get(force=True) if you
  need a fresh check right now (e.g. right before a long operation).
"""

import time
import socket
import logging
from dataclasses import dataclass

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("router")

# How long a cached online/offline result is trusted before we re-check.
POLL_INTERVAL = 10  # seconds

# Endpoint used for the connectivity probe. generate_204 returns an
# empty 204 response — tiny payload, fast, doesn't need auth.
_PROBE_URL = "https://www.gstatic.com/generate_204"
_PROBE_TIMEOUT = 3  # seconds — must be short so a dead connection
                     # doesn't stall the whole assistant


@dataclass(frozen=True)
class RouteState:
    is_online: bool
    main_ai: str     # "gemini" | "ollama"
    vision: str       # "openrouter" | "ollama"
    stt: str          # "openrouter_whisper" | "faster_whisper"


class Router:
    """Central online/offline + provider router. Use the module-level
    singleton `router` below instead of instantiating this yourself."""

    def __init__(self) -> None:
        self._last_check_ts: float = 0.0
        self._last_state: RouteState = self._build_state(is_online=False)

    # ---- public API --------------------------------------------------

    def get(self, force: bool = False) -> RouteState:
        """Return the current RouteState, using a cached result unless
        it's stale (older than POLL_INTERVAL) or force=True."""
        now = time.time()
        if force or (now - self._last_check_ts) >= POLL_INTERVAL:
            online = self._check_internet()
            self._last_state = self._build_state(is_online=online)
            self._last_check_ts = now
            logger.info(
                f"[router] status={'ONLINE' if online else 'OFFLINE'} "
                f"main_ai={self._last_state.main_ai} "
                f"vision={self._last_state.vision} "
                f"stt={self._last_state.stt}"
            )
        return self._last_state

    def is_online(self, force: bool = False) -> bool:
        return self.get(force=force).is_online

    # ---- internals ------------------------------------------------

    @staticmethod
    def _build_state(is_online: bool) -> RouteState:
        if is_online:
            return RouteState(
                is_online=True,
                main_ai="gemini",
                vision="openrouter",
                stt="openrouter_whisper",
            )
        return RouteState(
            is_online=False,
            main_ai="ollama",
            vision="ollama",
            stt="faster_whisper",
        )

    @staticmethod
    def _check_internet() -> bool:
        # Fast path: DNS resolution first. If DNS itself fails there's
        # no point attempting an HTTP request.
        try:
            socket.setdefaulttimeout(_PROBE_TIMEOUT)
            socket.gethostbyname("www.gstatic.com")
        except OSError:
            return False

        try:
            resp = requests.get(_PROBE_URL, timeout=_PROBE_TIMEOUT)
            # generate_204 returns HTTP 204 with an empty body.
            return resp.status_code == 204
        except requests.RequestException:
            return False


# Module-level singleton — import this everywhere else.
router = Router()


if __name__ == "__main__":
    # Manual test harness for Phase 1.
    # Run this, watch the output, then:
    #   1. Turn off Wi-Fi/data -> should print OFFLINE within POLL_INTERVAL
    #   2. Turn it back on      -> should print ONLINE within POLL_INTERVAL
    print("router.py manual test — Ctrl+C to stop")
    print(f"Polling every {POLL_INTERVAL}s. Toggle your network to test.\n")
    try:
        while True:
            state = router.get(force=True)
            print(
                f"online={state.is_online:<5} "
                f"main_ai={state.main_ai:<8} "
                f"vision={state.vision:<10} "
                f"stt={state.stt}"
            )
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nstopped.")