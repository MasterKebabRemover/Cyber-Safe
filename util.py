#!/usr/bin/python
import Cookie
import random
import logging

import constants

class ClientError(RuntimeError):
    def __init__(
        self,
        message,
    ):
        super(ClientError, self).__init__(message)

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