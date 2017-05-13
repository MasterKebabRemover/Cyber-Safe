#!/usr/bin/python
import errno
import logging
import os

import constants
from service_base import ServiceBase


class GetMenuService(ServiceBase):
    @staticmethod
    def name():
        return "/"

    def before_response_status(
        self,
        request_context,
    ):
        # try:
        self._fd = os.open(
            request_context["app_context"]["base"] +
            "/menu.html",
            os.O_RDONLY,
            0o666)
        request_context["headers"][constants.CONTENT_LENGTH] = os.fstat(
            self._fd).st_size
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        # except OSError as e:
        # if e.errno != errno.ENOENT:
        # raise

        return True

    def response(
        self,
        request_context,
    ):

        buf = ""
        try:
            while len(request_context["response"]) < constants.BLOCK_SIZE:
                buf = os.read(self._fd, constants.BLOCK_SIZE)
                if not buf:
                    break
                request_context["response"] += buf

            if buf:
                return constants.RETURN_AND_WAIT
            os.close(self._fd)

        except Exception as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
