#!/usr/bin/python
import os
import logging

import constants
import util
import urlparse
from service_base import ServiceBase

class BlockDeviceRead(ServiceBase):
    @staticmethod
    def name():
        return "/read"

    def before_response_status(
        self,
        request_context,
    ):
        sparse_size = os.stat(request_context["application_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if block >= sparse_size / constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Invalid block number")
        else:
            request_context["block"] = block

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = constants.BLOCK_SIZE

    def response(
        self,
        request_context,
    ):
        if request_context["block"] is not None:
            data = ""
            with util.FDOpen(
                request_context["application_context"]["sparse"],
                os.O_RDONLY,
            ) as fd:
                os.lseek(
                    fd,
                    constants.BLOCK_SIZE*request_context["block"],
                    os.SEEK_SET,
                )
                while len(data) < constants.BLOCK_SIZE:
                    read_buffer = os.read(fd, constants.BLOCK_SIZE - len(data))
                    if not read_buffer:
                        break
                    data += read_buffer
            request_context["block"] = None
            request_context["response"] = data
