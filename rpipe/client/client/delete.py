from __future__ import annotations
from typing import TYPE_CHECKING
from logging import getLogger

from .util import request

if TYPE_CHECKING:
    from .data import Config


def delete(conf: Config) -> None:
    """
    Delete the channel
    """
    getLogger("delete").info("Deleting channel %s", conf.channel)
    r = request("DELETE", conf.channel_url())
    if not r.ok:
        raise RuntimeError(r)


class DeleteOnFail:
    def __init__(self, config: Config):
        self.catch = KeyboardInterrupt | Exception
        self.config = config
        self.armed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.armed and isinstance(exc_val, self.catch):
            getLogger("DeleteOnFail").warning("Caught %s; deleting channel", type(exc_val))
            delete(self.config)
