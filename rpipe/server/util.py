from __future__ import annotations
from logging import getLogger, Logger, DEBUG
from typing import TYPE_CHECKING
from dataclasses import fields
from threading import RLock

from .constants import PIPE_MAX_BYTES

from flask import Response

if TYPE_CHECKING:
    from enum import Enum
    from typing import TypeVar, Any
    from collections.abc import Callable, Iterable
    from ..shared import UploadRequestParams, DownloadRequestParams

if TYPE_CHECKING:
    ArgsT = TypeVar("ArgsT", bound=Callable)


class Boolean:
    """
    A mutable boolean
    """

    def __init__(self, value: bool):
        self.value = value

    def __bool__(self) -> bool:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


class Singleton(type):
    """
    A metaclass that makes a class a singleton
    """

    _instances: dict[type, Any] = {}
    _lock = RLock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


def plaintext(msg: str, status: Enum | int = 200, **kwargs) -> Response:
    """
    Return a plain text Response containing the arguments
    """
    code: int = status if isinstance(status, int) else status.value
    return Response(msg, status=code, mimetype="text/plain", **kwargs)


def hsize(n: int) -> str:
    """
    Convert n (number of bytes) into a string such as: 12.3 MiB
    """
    sizes = (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10))
    for i, k in sizes:
        if n > k:
            return f"{n/k:.2f} {i}"
    return f"{n} B"


def pipe_full(data: Iterable[bytes]) -> bool:
    """
    :return: True if the pipe is full, else False
    """
    return sum(len(i) for i in data) >= PIPE_MAX_BYTES


def log_pipe_size(log: Logger, data: Iterable[bytes]) -> None:
    if not log.isEnabledFor(DEBUG):
        return
    n = sum(len(i) for i in data)
    msg = "Pipe now contains %s/%s bytes. It is %.2f%% full."
    log.debug(msg, hsize(n), hsize(PIPE_MAX_BYTES), 100 * n / PIPE_MAX_BYTES)


def log_params(log: Logger, p: UploadRequestParams | DownloadRequestParams) -> None:
    if not log.isEnabledFor(DEBUG):
        return
    log.debug("Request URL parameters:")
    for i in (k.name for k in fields(p)):
        log.debug("  %s: %s", i, getattr(p, i))


def _log_response(log: Logger, r: Response) -> None:
    if not log.isEnabledFor(DEBUG):
        return
    log.debug("Response:")
    log.debug("  Headers:")
    for i, k in r.headers.items():
        log.debug("    %s: %s", i, k)
    log.debug("  Status: %s", r.status)


def log_response(log_name: str = "util"):
    """
    A decorator that logs the returned flask Responses to the log log_name
    """

    def decorator(func: Callable[[ArgsT], Response]) -> Callable[[ArgsT], Response]:
        def inner(*args, **kwargs) -> Response:
            ret: Response = func(*args, **kwargs)
            _log_response(getLogger(log_name), ret)
            return ret

        return inner

    return decorator
