#!/usr/bin/python
import argparse
import logging
import os
import resource
import signal

import async_server
import constants
import event_object
import util
from http_socket import HttpSocket


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
        "--bind-address",
        default="0.0.0.0",
        help="Server bind address. Default: %(default)s",
    )
    parser.add_argument(
        "--bind-port",
        type=int,
        default=8888,
        help="Initial server bind port. Default: %(default)s",
    )
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
        default=None,
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
    parser.add_argument(
        "--max-buffer-size",
        type=int,
        default=1024*4,
        help="max size of async_server read buffer. Default: %(default)s",
    )
    parser.add_argument(
        "--sparse-file",
        default="disk",
        help="Name of sparse file",
    )
    parser.add_argument(
        "--sparse-size",
        type=int,
        default=constants.BLOCK_SIZE*32768,
        help="size of sparse file in MB"
    )
    parser.add_argument(
        "--block-device",
        action="store_true",
        default=False,
        help="whether this is a block device or frontend",
    )
    parser.add_argument(
        "--block-device-address",
        default="0.0.0.0",
        help="address of block device servers",
    )
    parser.add_argument(
        "--block-device-port",
        type=int,
        default=7777,
        help="port of first block device server"
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
        os.write(sparse, bytearray([1, 1])) # for bitmap and directory root


def __main__():
    args = parse_args()

    if args.block_device:
        init_block_device(
            args.sparse_file,
            args.sparse_size,
        )
        args.bind_address = args.block_device_address
        args.bind_port = args.block_device_port
    
    if args.foreground:
        daemonize()

    objects = []

    def terminate(signum, frame):
        for o in objects:
            o.stop(signum, frame)

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    logging.basicConfig(filename=args.log_file, level=logging.DEBUG)

    poll_object = {
            "poll": event_object.PollEvents,
            "select": event_object.SelectEvents,
        }[args.event_method]

    application_context = {
        "log": args.log_file,
        "event_object": poll_object,
        "bind_address": args.bind_address,
        "bind_port": args.bind_port,
        "timeout": args.timeout,
        "max_connections": args.max_connections,
        "max_buffer_size": args.max_buffer_size,
        "sparse": args.sparse_file,
        "block_device": args.block_device,
        "args": args,
    }

    server = async_server.Server(
        application_context,
    )
    server.add_listener(
        args.bind_address,
        args.bind_port,
        HttpSocket,
    )

    objects.append(server)
    logging.debug("main module called - server.run()")
    server.run()

if __name__ == "__main__":
    __main__()

# /http://localhost:8888/file.txt
