#!/usr/bin/python
import errno
import logging
import os

import constants
import util
from service_base import ServiceBase

class GetFileService(ServiceBase):
    @staticmethod
    def name():
        return "*"

    def before_response_status(
        self,
        request_context,
    ):
        filename = os.path.normpath(
            os.path.join(
                request_context["app_context"]["base"],
                request_context["parsed"].path[1:],
            )
        )
        base = request_context["app_context"]["base"]
        if filename[:-len(request_context["parsed"].path)] != os.path.normpath(base):
            raise RuntimeError("Malicious URI %s" % request_context["parsed"].path)
        try:
            self._fd = os.open(filename, os.O_RDONLY, 0o666)
            request_context["headers"][constants.CONTENT_LENGTH] = os.fstat(self._fd).st_size
            request_context["headers"][constants.CONTENT_TYPE] = constants.MIME_MAPPING.get(
                os.path.splitext(
                    filename
                )[1].lstrip('.'),
                constants.MIME_MAPPING["*"],
            )
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise util.HTTPError(500, "Internal Error", "File %s not found" % filename)
            if e.errno != errno.ENOENT:
                raise

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
            logging.debug(e)
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise