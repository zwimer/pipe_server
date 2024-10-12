from __future__ import annotations
from typing import TYPE_CHECKING
from logging import getLogger
from json import dumps

from zstandard import ZstdCompressor

from ...shared import TRACE, QueryEC, Version, version
from .util import REQUEST_TIMEOUT, request
from .errors import UsageError, VersionError
from .data import Config, Mode
from .delete import delete
from .recv import recv
from .send import send

if TYPE_CHECKING:
    from pathlib import Path


_LOG: str = "client"
_DEFAULT_LVL: int = 3


def _print_config(conf: Config, config_file: Path) -> None:
    log = getLogger(_LOG)
    log.info("Mode: print-config")
    print(f"Path: {config_file}")
    print(conf)
    try:
        conf.validate()
        log.info("Config validated")
    except UsageError as e:
        log.warning("Config invalid %s", e)


def _check_outdated(conf: Config) -> None:
    log = getLogger(_LOG)
    log.info("Mode: Outdated")
    r = request("GET", f"{conf.url}/supported")
    if not r.ok:
        raise RuntimeError(f"Failed to get server minimum version: {r}")
    info = r.json()
    log.info("Server supports clients: %s", info)
    ok = Version(info["min"]) <= version and all(version != Version(i) for i in info["banned"])
    print(f"{'' if ok else 'NOT '}SUPPORTED")


def _query(conf: Config) -> None:
    log = getLogger(_LOG)
    log.info("Mode: Query")
    if not conf.channel:
        raise UsageError("Channel unknown; try again with --channel")
    log.info("Querying channel %s ...", conf.channel)
    r = request("GET", f"{conf.url}/q/{conf.channel}")
    log.debug("Got response %s", r)
    log.log(TRACE, "Data: %s", r.content)
    match r.status_code:
        case QueryEC.illegal_version:
            raise VersionError(r.text)
        case QueryEC.no_data:
            print(f"No data on channel: {conf.channel}")
            return
    if not r.ok:
        raise RuntimeError(f"Query failed. Error {r.status_code}: {r.text}")
    print(f"{conf.channel}: {dumps(r.json(), indent=4)}")


def _priority_actions(conf: Config, mode: Mode, config_file: Path) -> None:
    log = getLogger(_LOG)
    if mode.print_config:
        _print_config(conf, config_file)
        return
    if mode.save_config:
        log.info("Mode: Save Config")
        conf.save(config_file)
        return
    # Everything after this requires the URL
    if conf.url is None:
        raise UsageError("Missing: URL")
    # Remaining priority modes
    if mode.outdated:
        _check_outdated(conf)
    if mode.server_version:
        log.info("Mode: Server Version")
        r = request("GET", f"{conf.url}/version")
        if not r.ok:
            raise RuntimeError(f"Failed to get version: {r}")
        print(f"rpipe_server {r.text}")
    if mode.query:
        _query(conf)


def rpipe(conf: Config, mode: Mode, config_file: Path) -> None:
    """
    rpipe: A remote piping tool
    :param conf: Configuration for the remote pipe, may be invalid at this point
    :param config_file: Path to the configuration file, may not exist
    :param mode: Mode to operate in, assumes flags are valid and within expected ranges
    """
    log = getLogger(_LOG)
    if mode.priority():
        _priority_actions(conf, mode, config_file)
        return
    conf.validate()
    if (mode.read or mode.write) and not conf.password:
        log.warning("Encryption disabled: plaintext mode")
        if mode.zstd is not None:
            raise UsageError("Cannot compress data in plaintext mode")
    # Invoke mode
    log.info("HTTP timeout set to %d seconds", REQUEST_TIMEOUT)
    if mode.read:
        recv(conf, mode.block, mode.peek, mode.force, mode.progress)
    elif mode.write:
        lvl = _DEFAULT_LVL if mode.zstd is None else mode.zstd
        log.debug("Using compression level %d and %d threads", lvl, mode.threads)
        compress = ZstdCompressor(write_checksum=True, level=lvl, threads=mode.threads).compress
        send(conf, mode.ttl, mode.progress, compress)
    else:
        delete(conf)
