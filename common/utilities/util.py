## @package cyber-safe.common.utilities.util
#
# Various utility functions and classes.
#
import Cookie
import errno
import random
import logging
import traceback
import socket
import os

from common import constants

STATUS_CODES = {
    200: "OK",
    307: "Temporary Redirect",
    401: "Unauthorized",
    404: "File Not Found",
    500: "Internal Error",
}

## HTTP Error class.
# Error class to rise when something goes wrong with HTTP.
#
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

## FD Open class.
# Allowes using python "with" function when reading from file descriptors.
#
class FDOpen(object):
    def __init__(
        self,
        file,
        flags,
        mode=None,
    ):
        self._file = file
        self._flags = flags
        self._mode = mode

    def __enter__(self):
        self._fd = None
        self.fd = None
        if self._mode:
            self._fd = self.fd = os.open(
                self._file,
                self._flags,
                self._mode,
            )
        else:
            self._fd = self.fd = os.open(
                self._file,
                self._flags,
            )
        return self.fd

    def __exit__(self, type, value, traceback):
        if self._fd:
            os.close(self._fd)

## Text to html convert.
# @param text (str) text.
# @returns (str) html format text.
def text_to_html(
    text,
):
    return ("<HTML>\r\n<BODY>\r\n%s\r\n</BODY>\r\n</HTML>" % text)

## Text to css convert.
# @param text (str) text.
# @param error (bool) whether to color text as error.
# @returns (str) css format text.
def text_to_css(
    text,
    error=False,
):
    return (
        constants.RESPONSE_CSS +
        '<h1 %s>%s</h1>' % ('class="error"' * error, text) +
        constants.BACK_TO_MENU
    )

## Cookie parsing.
# @param string (str) string to parse cookie from.
# @param cookie (str) cookie name.
# @returns (str) value of cookie from stirng, if exists.
def parse_cookies(string, cookie):
    if string is None:
        return None
    c = Cookie.SimpleCookie()
    c.load(string)
    if c.get(cookie) is None:
        return None
    return c.get(cookie).value

## Parse header.
# @param line (str) line.
# @returns (tuple) line splitted to header name and header value, if line is legal header format.
def parse_header(line):
    SEP = ':'
    n = line.find(SEP)
    if n == -1:
        raise RuntimeError('Invalid header received')
    return line[:n].rstrip(), line[n + len(SEP):].lstrip()

## Receive line.
# @param buffer (str) buffer.
# @returns (tuple) first line parsed from buffer and rest of the buffer.
def recv_line(
    buffer
):
    n = buffer.find(constants.CRLF_BIN)
    if n == -1:
        return None, buffer

    result = buffer[:n]
    buffer = buffer[n + len(constants.CRLF_BIN):]
    return result, buffer

## Get headers.
# @param request_context (dict) request context.
# @return (bool) whether finished parsing.
#
# function is used by some HTTP objects to turn received data buffer into dictionary
# containing wanted headers and their values.
#
def get_headers(
    request_context,
):
    finished = False
    for i in range(constants.MAX_NUMBER_OF_HEADERS):
        line, request_context["recv_buffer"] = recv_line(
            request_context["recv_buffer"])
        if line is None:
            break
        if line == "":
            finished = True
            break
        line = parse_header(line)
        if line[0] in request_context["req_headers"]:
            request_context["req_headers"][line[0]] = line[1]
    else:
        raise RuntimeError("Exceeded max number of headers")
    return finished

## Send headers.
# @param request_context (dict) request context.
# @returns (bool) true.
#
# Used by some HTTP objects to convert dictionary of header names and values from request context to
# string buffer that is later sent in HTTP communication.
#
def send_headers(
    request_context,
):
    for key, value in request_context["headers"].iteritems():
        request_context["send_buffer"] += (
            "%s: %s\r\n" % (key, value)
        )
    request_context["send_buffer"] += ("\r\n")
    return True

## Receive buffer
# @param entry (Pollable) entry.
#
# receives data from entry socket and puts it in entry receive buffer for later use.
#
def receive_buffer(entry):
    free_buffer_size = constants.BLOCK_SIZE - len(
        entry.request_context["recv_buffer"]
    )
    try:
        t = entry.socket.recv(free_buffer_size)
        if not t:
            raise Disconnect(
                'Disconnected while recieving content'
            )
        entry.request_context["recv_buffer"] += t
    except socket.error as e:
        traceback.print_exc()
        if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
            raise

## Add status.
# @param entry (Pollable) entry.
# @param code (int) status code).
# @param extra (str) extra information about status.
#
# adds a status line to entry send buffer according to received status code.
#
def add_status(entry, code, extra):
    if not entry.request_context.get("status_sent"):
        entry.request_context["code"] = code
        entry.request_context["status"] = STATUS_CODES.get(code, 500)
    else:
        entry.request_context["send_buffer"] += ((
            "%s %s %s\r\n"
        ) % (
            constants.HTTP_SIGNATURE,
            code,
            STATUS_CODES[code],
        )
        ).encode("utf-8")

## Random pad function.
# @param data (str) data to pad.
# @param length (int) length to pad for.
# @returns (int) data padded until length with random bytes.
#
def random_pad(data, length):
    b = bytearray(data)
    b += os.urandom(length - len(b))
    return b