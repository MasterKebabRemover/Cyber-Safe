#!/usr/bin/python
import logging
import os

import constants
import util
import urlparse
from service_base import ServiceBase

class BlockDeviceWrite(ServiceBase):
    @staticmethod
    def name():
        return "/write"

    def before_request_content(
        self,
        request_context,
    ):
        super(BlockDeviceWrite, self).before_request_content(request_context)
        sparse_size = os.stat(request_context["app_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if block >= sparse_size / constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Invalid block number")
        elif int(
            request_context["req_headers"].get("Content-Length")
        ) > constants.BLOCK_SIZE:
            raise HTTPError(500, "Content exceeds block size")
        else:
            request_context["block"] = block
            self._data = ""


    def handle_content(
        self,
        request_context,
    ): # first construct data, then write all at once
        request_context["content_length"] -= len(request_context["recv_buffer"])
        self._data += request_context["recv_buffer"]
        request_context["recv_buffer"] = ""

        if request_context["content_length"] > 0:
            return False

        with util.FDOpen(
                request_context["app_context"]["sparse"],
                os.O_WRONLY,
            ) as fd:
                os.lseek(
                    fd,
                    constants.BLOCK_SIZE*request_context["block"],
                    os.SEEK_SET,
                )
                while self._data:
                    self._data = self._data[os.write(fd, self._data):]
        return None
