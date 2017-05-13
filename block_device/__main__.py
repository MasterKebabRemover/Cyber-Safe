#!/usr/bin/python
import argparse
import ConfigParser
import logging
import multiprocessing
import os
import resource
import signal

from common import async_server
from common import constants
from common import event_object
from common.utilities import util
from common.pollables.http_socket import HttpSocket


def daemonize():
    os.closerange(3, resource.RLIMIT_NOFILE)
    os.chdir('/')
    child = os.fork()
    if child != 0:
        os._exit(0)

    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    null = os.open(os.devnull, os.O_RDWR)
    for i in range(0, 3):
        os.dup2(null, i)
    os.close(null)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-connections",
        type=int,
        default=10,
        help="Number of connections the server accepts. Default: %(default)s",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional file to log into",
    )
    parser.add_argument(
        "--base",
        default=constants.BASE,
        help="base location of files",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Optional server polling timeout",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        default=False,
        help="Whether to daemonize program. Default: %(default)s",
    )
    parser.add_argument(
        "--event-method",
        help="whether to use select instead of poll. Default: %s" % (
            "select" if os.name == "nt" else "poll"
        ),
        choices=["select", "poll"],
        default="select" if os.name == "nt" else "poll"
    )

    args = parser.parse_args()
    args.base = os.path.normpath(os.path.realpath(args.base))
    return args


def init_block_device(filename, filesize):
    with util.FDOpen(
        filename,
        os.O_RDWR | os.O_CREAT,
        0o666,
    ) as sparse:
        os.lseek(sparse, filesize, 0)
        os.write(sparse, bytearray(constants.BLOCK_SIZE))
        os.lseek(sparse, 0, 0)


def __main__():
    # parse args
    args = parse_args()
    logging.basicConfig(filename=args.log_file, level=logging.DEBUG)

    Config = ConfigParser.ConfigParser()
    Config.read(constants.BLOCK_DEVICE_CONFIG)

    init_block_device(
        Config.get('blockdevice', 'file.name'),
        Config.getint('blockdevice', 'file.size'),
    )
    bind_address = Config.get('blockdevice', 'bind.address')
    bind_port = Config.getint('blockdevice', 'bind.port')
    sparse = Config.get('blockdevice', 'file.name')
    admin = None

    if args.foreground:
        daemonize()

    objects = []

    def terminate(signum, frame):
        for o in objects:
            o.stop(signum, frame)

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    poll_object = {
        "poll": event_object.PollEvents,
        "select": event_object.SelectEvents,
    }[args.event_method]

    app_context = {
        "log": args.log_file,
        "event_object": poll_object,
        "bind_address": bind_address,
        "bind_port": bind_port,
        "timeout": args.timeout,
        "max_connections": args.max_connections,
        "sparse": sparse,
        "block_device": True,
        "config": Config,
        "admin": admin,
        "base": args.base,
        "password_dict": {},
        # for disk read/write control
        "semaphore": multiprocessing.BoundedSemaphore(constants.MAX_SEMAPHORE),
    }

    server = async_server.Server(
        app_context,
    )
    server.add_listener(
        bind_address,
        bind_port,
        HttpSocket,
    )

    objects.append(server)
    logging.debug("main module called - server.run()")
    server.run()


if __name__ == "__main__":
    __main__()