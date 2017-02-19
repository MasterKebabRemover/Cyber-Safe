#!/usr/bin/python
import os

import constants
import util
import urlparse
from service_base import ServiceBase

class BlockDeviceWrite(ServiceBase):
    @staticmethod
    def name():
        return "/write"

    def __init__(
        self,
    ):
        super(BlockDeviceWrite, self).__init__()

    def before_request_content(
        self,
        request_context,
    ):
        super(BlockDeviceWrite, self).before_request_content(request_context)
        sparse_size = os.stat(request_context["application_context"]["sparse"]).st_size
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
            request_context["fd"] = os.open(
                request_context["application_context"]["sparse"],
                os.O_WRONLY,
            )
            os.lseek(
                request_context["fd"],
                constants.BLOCK_SIZE*request_context["block"],
                os.SEEK_SET,
            )


    def handle_content(
        self,
        request_context,
    ):
        while request_context["content"]:
            request_context["content"] = request_context["content"][os.write(
                request_context["fd"],
                request_context["content"],
            ):]
        
    def before_terminate(
        self,
        request_context,
    ):
        if request_context.get("fd"):
            os.close(request_context["fd"])
