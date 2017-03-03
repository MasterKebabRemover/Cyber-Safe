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

def get_headers(
        request_context,
    ):
        finished = False
        for i in range(constants.MAX_NUMBER_OF_HEADERS):
            line, request_context["recv_buffer"] = recv_line(request_context["recv_buffer"])
            # logging.debug(line)
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

def get_content(
    request_context,
):
    if request_context["content_length"]:
        data = request_context["recv_buffer"][:min(
            request_context["content_length"],
            constants.BLOCK_SIZE - len(request_context["content"]),
        )]
        request_context["content"] += data
        request_context["content_length"] -= len(data)
        request_context["recv_buffer"] = request_context["recv_buffer"][len(data):]