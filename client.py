#!/usr/bin/python
import argparse
import contextlib
import logging
import socket

import constants

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dst-address",
        default="0.0.0.0",
        help="Server bind address. Default: %(default)s",
    )
    parser.add_argument(
        "--dst-port",
        type=int,
        default=8888,
        help="Initial server bind port. Default: %(default)s",
    )
    parser.add_argument(
        "--action",
        choices=["read", "write"],
        default="read",
        help="Whether to read or write from block device",
    )
    parser.add_argument(
        "--block",
        type=int,
        default=0,
        help="Which block to read/write from",
    )
    args = parser.parse_args()
    return args

def send_string(socket, string):
    while string:
        string = string[socket.send(string):]

def main():
    args = parse_args()
    logging.basicConfig(filename=None, level=logging.DEBUG)

    with contextlib.closing(
        socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    ) as s:
        s.connect((args.dst_address, args.dst_port))
        if args.action == "read":
            cmd = "GET /%s?block=%d %s\r\n\r\n" % (
                args.action,
                args.block,
                constants.HTTP_SIGNATURE
            )
            send_string(s, cmd)
        while True:
            logging.debug(s.recv(constants.BLOCK_SIZE))
        # line = prot.get_line()
        # if line[:len(constants.HTTP)] != constants.HTTP:
                # raise RuntimeError("Wrong HTTP Version!")
        # code = line[len(constants.HTTP)+1:]
        # if code != constants.SUCCESS_CODE:
            # raise Exception("Invalid HTTP response: %s" % (code))

        # line_counter = constants.MAX_NUMBER_OF_HEADERS
        # content_length = 0
        # while True:
                # line = prot.get_line()
                # line_counter -= 1
                # if line_counter < 0:
                    # raise RuntimeError("Too many lines!")
                # if not line:
                    # break
                # if prot.split_line(line)["header"] == "Content-Length":
                    # content_length = int(prot.split_line(line)["content"])
        # receive_to_output(handle, temp_file, s, content_length)
        # os.close(handle)
        # os.rename(temp_file, OUTPUT)
        # print code
        # temp_file = None
    # except Exception as e:
        # print(e)
    # finally:
        # if temp_file is not None:
            # try:
                # os.remove(temp_file)
            # except Exception as e:
                # print("Can't remove file '%s': %s" % (temp_file, e))

main()
