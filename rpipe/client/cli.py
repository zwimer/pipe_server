from __future__ import annotations
from multiprocessing import cpu_count
from pathlib import Path
import argparse

from .. import __version__  # Extract version without importing shared


PASSWORD_ENV: str = "RPIPE_PASSWORD"
_DEFAULT_CF = Path.home() / ".config" / "rpipe.json"
_SI_UNITS: str = "KMGT"


def _cli(parser: argparse.ArgumentParser, parsed: argparse.Namespace) -> None:
    """
    We import main from CLI after parsing arguments because
    it is slow, and not necessary for --help or --version
    """
    # pylint: disable=import-outside-toplevel,cyclic-import
    from .main import main

    main(parser, parsed)


def _si_parse(size: str) -> int:
    if size.isdecimal():
        return int(size)
    try:
        if (frv := float(size[:-1]) * (1000 ** (1 + _SI_UNITS.index(size[-1].upper())))) == (rv := int(frv)):
            return int(rv)
    except ValueError as e:
        raise ValueError(f"Invalid size: {size}") from e
    raise ValueError(f"Invalid size: {size}")


# pylint: disable=too-many-locals,too-many-statements
def cli() -> None:
    """
    Parses arguments then invokes rpipe
    """
    cpu = cpu_count()
    threads = max(1, cpu - 1)
    parser = argparse.ArgumentParser(add_help=False)
    parser.set_defaults(method=None)
    read_g = parser.add_argument_group("Read Options")
    read_g.add_argument(
        "-b", "--block", action="store_true", help="Wait until a channel is available to read"
    )
    read_g.add_argument(
        "-p",
        "--peek",
        action="store_true",
        help="Read pipe without emptying it; will not construct a persistent pipe like a normal read",
    )
    read_g.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Attempt to read data even if this is a upload/download client version mismatch",
    )
    write_g = parser.add_argument_group("Write Options")
    write_g.add_argument(
        "-t",
        "--ttl",
        type=int,
        default=None,
        help="Pipe TTL in seconds; use server default if not passed",
    )
    write_g.add_argument(  # Do not use default= for better error checking w.r.t. plaintext mode
        "--zstd",
        metavar="[1-22]",
        choices=range(1, 23),
        type=int,
        help="Compression level to use; invalid in plaintext mode",
    )
    write_g.add_argument(
        "--threads",
        metavar=f"[1-{cpu}]" if cpu > 1 else "1",
        choices=range(1, cpu + 1),
        default=threads,
        type=int,
        help=f"The number of threads to use for compression. Default: {threads}",
    )
    delete_g = parser.add_argument_group("Delete Options")
    delete_g.add_argument("-d", "--delete", action="store_true", help="Delete all entries in the channel")
    read_write_g = parser.add_argument_group("Read/Write Options")
    # pylint: disable=duplicate-code
    read_write_g.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase Log verbosity, pass more than once to increase verbosity",
    )
    msg = (
        "Show a progress bar, if a value is passed, assume that's the number"
        " of bytes to be passed. Only valid while sending or receiving data."
        " Values can be suffixed with K, M, G, or T, to multiply by powers of 1000"
    )
    read_write_g.add_argument(
        "-P", "--progress", metavar="SIZE", type=_si_parse, default=False, const=True, nargs="?", help=msg
    )
    # Config options
    config = parser.add_argument_group("Config Options")
    config.add_argument("-u", "--url", help="The pipe url to use")
    config.add_argument("-c", "--channel", help="The channel to use")
    config.add_argument(
        "-k",
        "--key-file",
        type=Path,
        help="SSH ed25519 private key file used to signed admin requests",
    )
    config.add_argument("-C", "--config-file", type=Path, default=_DEFAULT_CF, help="The custom config file")
    config.add_argument(
        "-e",
        "--encrypt",
        action=argparse.BooleanOptionalAction,
        help=f"Encrypt the data; uses {PASSWORD_ENV} as the password if set, otherwise uses saved password",
    )
    config.add_argument("-s", "--ssl", action=argparse.BooleanOptionalAction, help="Require host use https")
    # Priority Modes
    priority_mode = parser.add_argument_group(
        "Alternative Modes",
        "If one of these is passed, the client will execute the desired action then exit",
    ).add_mutually_exclusive_group()
    priority_mode.add_argument("-h", "--help", action="help", help="show this help message and exit")
    priority_mode.add_argument("-V", "--version", action="version", version=f"{parser.prog} {__version__}")
    priority_mode.add_argument(
        "-X", "--print-config", action="store_true", help="Print out the config (including CLI args)"
    )
    priority_mode.add_argument(
        "-S",
        "--save-config",
        action="store_true",
        help="Update the existing rpipe config then exit; allows incomplete configs to be saved",
    )
    priority_mode.add_argument(
        "-O", "--outdated", action="store_true", help="Check if this client is too old for the server"
    )
    priority_mode.add_argument("-Q", "--server-version", action="store_true", help="Print the server version")
    priority_mode.add_argument(
        "-q",
        "--query",
        action="store_true",
        help="Get information on the given channel",
    )
    priority_mode.add_argument("-A", "--admin", action="store_true", help="Allow use of admin commands")
    # Admin commands
    admin = parser.add_subparsers(
        title="Admin Commands",
        description=(
            "Server admin commands; must be used with --admin and should have a key file set before use."
            " All arguments except --verbose, config arguments are ignored with admin commands."
            " Server must be configured to accept messages signed by your selected private key file"
        ),
        dest="method",
    )
    admin.add_parser("debug", help="Check if the server is running in debug mode")
    admin.add_parser("channels", help="List all channels with stats")
    admin.add_parser("stats", help="Print various server stats")
    log_p = admin.add_parser("log", help="Download server logs various server stats")
    log_p.add_argument(
        "-o", "--output-file", type=Path, default=None, help="Log output file, instead of stdout"
    )
    log_lvl_p = admin.add_parser("log-level", help="Get/set the server log level")
    log_lvl_p.add_argument("level", default=None, nargs="?", help="The log level for the server to use")
    _cli(parser, parser.parse_args())
