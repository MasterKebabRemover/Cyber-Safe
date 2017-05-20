#!/usr/bin/python
import logging
import os
import urlparse

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase
from common.utilities import encryption_util


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
        logging.debug(block)
        if block >= sparse_size / constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Invalid block number")
        elif int(
            request_context["req_headers"].get("Content-Length")
        ) > constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Content exceeds block size")
        else:
            request_context["block"] = block
            self._data = bytearray(0)

    def handle_content(
        self,
        request_context,
    ):  # first construct data, then write all at once
        request_context["content_length"] -= len(
            request_context["recv_buffer"])
        self._data += request_context["recv_buffer"]
        request_context["recv_buffer"] = ""

        if request_context["content_length"] > 0:
            return False

        # now encrypt data by block device keys
        aes = encryption_util.get_aes(
            key=request_context["app_context"]["config"].get(
                'blockdevice', 'key'),
            ivkey=request_context["app_context"]["config"].get(
                'blockdevice', 'ivkey'),
            block_num=request_context["block"],
        )
        self._data = encryption_util.encrypt_block_aes(aes, self._data)

        with util.FDOpen(
            request_context["app_context"]["sparse"],
            os.O_WRONLY,
        ) as fd:
            os.lseek(
                fd,
                constants.BLOCK_SIZE * request_context["block"],
                os.SEEK_SET,
            )
            while self._data:
                self._data = self._data[os.write(fd, self._data):]
        return None
