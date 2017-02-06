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

    def __init__(
        self,
    ):
        super(BlockDeviceRead, self).__init__()

    def before_response_status(
        self,
        request_context,
    ):

        sparse_size = os.stat(request_context["application_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if (sparse_size / (constants.BLOCK_SIZE)) - 1 < block:
            request_context["code"] = 500
            request_context["status"] = "Invalid block number"
        else:
            request_context["block"] = block

    def response(
        self,
        request_context,
    ):
        if request_context.get("block") is None:
            return
        sparse = os.open(request_context["application_context"]["sparse"], os.O_RDONLY)
        os.lseek(sparse, constants.BLOCK_SIZE*request_context["block"], os.SEEK_SET)
        data = os.read(sparse, constants.BLOCK_SIZE)
        os.close(sparse)
        request_context["block"] = None
        return data
