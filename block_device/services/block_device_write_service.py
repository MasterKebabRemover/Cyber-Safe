## @package cyber-safe.block_device.services.block_device_write_service
#
# Block device service for handling block write requests.
#
import logging
import os
import urlparse

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase
from common.utilities import encryption_util

## Block device write request handler class.
# receives requests with block number and block from authorized client and writes given block to desired index.
class BlockDeviceWrite(ServiceBase):
    ## Service name function.
    # @returns (str) service name.
    @staticmethod
    def name():
        return "/write"

    ## Function called before receiving HTTP content.
    #
    # checks client authorization and parses block index from query string.
    # also checks that block length and index parameters are valid and rises an error if not.
    #
    def before_request_content(
        self,
        request_context,
    ):
        if not encryption_util.check_login(request_context):
            raise util.HTTPError(401, "Unathorized", "Bad block device authentication")
        sparse_size = os.stat(request_context["app_context"]["sparse"]).st_size
        qs = urlparse.parse_qs(request_context["parsed"].query)
        block = int(qs['block'][0])
        if block >= sparse_size / constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Invalid block number")
        elif int(
            request_context["req_headers"].get("Content-Length")
        ) > constants.BLOCK_SIZE:
            raise util.HTTPError(500, "Content exceeds block size")
        else:
            request_context["block"] = block
            self._data = bytearray(0)

    ## Function called during receive of HTTP content.
    #
    # receives block content until the end.
    # encrypts block with AES and block device key.
    # writes encrypted block to disk.
    #
    def handle_content(
        self,
        request_context,
    ):
        request_context["content_length"] -= len(
            request_context["recv_buffer"])
        self._data += request_context["recv_buffer"]
        request_context["recv_buffer"] = ""

        if request_context["content_length"] > 0:
            return False

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


    ## Get header dictionary.
    # @returns (dict) dictionary of wanted headers to parse.
    def get_header_dict(
        self,
    ):
        return {
            constants.AUTHORIZATION: None,
            constants.CONTENT_LENGTH: 0,
        }
