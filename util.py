#!/usr/bin/python
import Cookie
import random
import logging
import os

import constants

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