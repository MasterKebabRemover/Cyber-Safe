#!/usr/bin/python
import Cookie
import errno
import random
import logging
import traceback
import socket
import os

import constants
from http_client import HttpClient

STATUS_CODES = {
    200 : "OK",
    401 : "Unauthorized",
    404 : "File Not Found",
    500 : "Internal Error",
}

class HTTPError(RuntimeError):
    def __init__(
        self,
        code,
        status,
        message="",
    ):
        super(HTTPError, self).__init__(message)
        self.code = code
        self.status = status
        self.message = message

class FDOpen(object):
    def __init__(
        self,
        file,
        flags,
        mode,
    ):
        self._file = file
        self._flags = flags
        self._mode = mode

    def __enter__(self):
        self._fd = None
        self.fd = None
        self._fd = self.fd = os.open(
            self._file,
            self._flags,
            self._mode,
        )
        return self.fd

    def __exit__(self, type, value, traceback):
        if self._fd:
            os.close(self._fd)

class Disconnect(RuntimeError):
    def __init__(self, desc = "Disconnect"):
        super(Disconnect, self).__init__(desc)

def text_to_html(
    text,
):
    return ("<HTML>\r\n<BODY>\r\n%s\r\n</BODY>\r\n</HTML>" % text).decode('utf-8')

def random_cookie():
    result = ""
    for i in range(0, 64):
        result += str(random.randint(0, 255))
    return result

def parse_cookies(string, cookie):
    if string == None:
        return None
    simple_cookie = Cookie.SimpleCookie(str(string)).get(cookie)
    if simple_cookie:
        return simple_cookie.value
    return None

def parse_header(line):
    SEP = ':'
    n = line.find(SEP)
    if n == -1:
        raise RuntimeError('Invalid header received')
    return line[:n].rstrip(), line[n + len(SEP):].lstrip()

def recv_line(
    buffer
):
    n = buffer.find(constants.CRLF_BIN)
    if n == -1:
        return None, buffer

    result = buffer[:n].decode("utf-8")
    buffer = buffer[n + len(constants.CRLF_BIN):]
    return result, buffer

def get_headers(
        request_context,
    ):
        finished = False
        for i in range(constants.MAX_NUMBER_OF_HEADERS):
            line, request_context["recv_buffer"] = recv_line(request_context["recv_buffer"])
            if line is None: # means that async server has yet to receive all headers
                break
            if line == "": # this is the end of headers
                finished = True
                break
            line = parse_header(line)
            if line[0] in request_context["req_headers"]:
                request_context["req_headers"][line[0]] = line[1]
        else:
            raise RuntimeError("Exceeded max number of headers")
        return finished

def send_headers(
    request_context,
):
    for key, value in request_context["headers"].iteritems():
        request_context["send_buffer"] += (
            "%s: %s\r\n" % (key, value)
        )
    request_context["send_buffer"] += ("\r\n")
    return True

def receive_buffer(entry):
    free_buffer_size = entry.request_context[
            "application_context"
        ][
            "max_buffer_size"
        ] - len(
            entry.request_context["recv_buffer"]
        )
    try:
        t = entry.socket.recv(free_buffer_size)
        if not t:
            raise Disconnect(
                'Disconnected while recieving content'
            )
        entry.request_context["recv_buffer"] += t

    except socket.error, e:
        traceback.print_exc()
        if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
            raise
            
def add_status(entry, code, extra):
    entry.request_context["code"] = code
    entry.request_context["status"] = STATUS_CODES[code]

def ljust_00(data, length):
    b = bytearray(data)
    while len(b) < length:
        b += chr(0)
    return b

def init_client(
    request_context,
    client_action,
    client_block_num,
):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = HttpClient(
        socket=s,
        state=constants.ACTIVE,
        application_context=request_context["application_context"],
        fd_dict=request_context["fd_dict"],
        action=client_action, # must be constants.READ or constants.WRITE
        block_num=client_block_num, # this is directory root
        parent=request_context["callable"],
    )
    try:
        s.connect(
            (
                request_context["application_context"]["args"].block_device_address,
                request_context["application_context"]["args"].block_device_port,
            )
        )
        s.setblocking(False)
    except Exception as e:
        if e.errno != errno.ECONNREFUSED:
            raise
        raise util.HTTPError(500, "Internal Error", "Block Device not found")
    request_context["fd_dict"][client.fileno()] = client
