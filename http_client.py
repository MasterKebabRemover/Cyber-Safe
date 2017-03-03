#!/usr/bin/python

from http_socket import HttpSocket

class HttpClient(HttpSocket):
    

# def send_string(socket, string):
    # while string:
        # string = string[socket.send(string):]

# def main():
    # args = parse_args()
    # logging.basicConfig(filename=None, level=logging.DEBUG)

    # with contextlib.closing(
        # socket.socket(
            # family=socket.AF_INET,
            # type=socket.SOCK_STREAM,
        # )
    # ) as s:
        # s.connect((args.dst_address, args.dst_port))
        # s.settimeout(1)
        # cmd = "GET /%s?block=%d %s\r\n" % (
                # args.action,
                # args.block,
                # constants.HTTP_SIGNATURE
            # )
        # if args.action == "read":
            # cmd += "\r\n"
            # send_string(s, cmd)
        # if args.action == "write":
            # cmd += "Content-Length: %s\r\n\r\n" % (len(DATA_TO_SEND))
            # send_string(s, cmd)
            # send_string(s, DATA_TO_SEND)
        # data = s.recv(constants.BLOCK_SIZE)
        # while data:
            # logging.debug(data)
            # data = s.recv(constants.BLOCK_SIZE)

# main()
