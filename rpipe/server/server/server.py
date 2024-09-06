from __future__ import annotations
from typing import TYPE_CHECKING
from os import environ
import logging

from ..util import Singleton
from .shutdown_handler import ShutdownHandler
from .prune_thread import PruneThread
from .state import State

if TYPE_CHECKING:
    from pathlib import Path


class Server(metaclass=Singleton):

    def __init__(self):
        self._log = logging.getLogger("server")
        self.state = State()

    def start(self, debug: bool, state_file: Path | None) -> None:
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            self._log.debug("root logger level set to DEBUG")
        with self.state as s:
            s.debug = debug
        self._log.debug("Initializing server")
        # Load state
        if state_file is not None:
            # Do not run on first load when in debug mode b/c of flask reloader
            if debug and environ.get("WERKZEUG_RUN_MAIN") != "true":
                msg = "State loading and shutdown handling disable on initial flask load on debug mode"
                self._log.info(msg)
            else:
                if state_file.exists():
                    self._log.debug("Detected state file %s", state_file)
                    with self.state as state:
                        state.load(state_file)
                self._log.debug("Installing shutdown handler")
                ShutdownHandler(self.state, state_file)
        self._log.debug("Starting prune thread")
        PruneThread(self.state).start()
        self._log.debug("Server initialization complete")
