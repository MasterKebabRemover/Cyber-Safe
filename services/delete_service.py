#!/usr/bin/python
import errno
import os
import tempfile
import logging
import socket
import struct
import urlparse

import constants
import util
from util import HTTPError
from service_base import ServiceBase
from http_client import HttpClient

class DeleteService(ServiceBase):
    @staticmethod
    def name():
        return "/delete"

    def __init__(
        self,
    ):
        super(DeleteService, self).__init__()
        self._bitmap = None
        self._root = None

    def before_request_content(
        self,
        request_context,
    ):
        qs = urlparse.parse_qs(request_context["parsed"].query)
        if not qs.get("filename"):
            raise util.HTTPError(500, "Internal Error", "file name missing")
        request_context["filename"] = str(qs["filename"][0])
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._after_bitmap
        util.init_client(
            request_context,
            client_action=constants.READ, 
            client_block_num=0,
        )

    def _after_bitmap(
        self,
        request_context,
    ):
        self._bitmap = bytearray(request_context["block"])
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._after_root
        util.init_client(
            request_context,
            client_action=constants.READ, 
            client_block_num=1,
        )

    def _after_root(
        self,
        request_context,
    ):
        self._root = bytearray(request_context["block"])
        request_context["block"] = ""

        # go over root and find file's entry, raise error if not found
        index = 0
        dir_num = None
        while index < len(self._root):
            current_name = bytearray(self._root[index:index + constants.FILENAME_LENGTH])
            current_name = current_name.rstrip('\x00')
            if current_name == request_context["filename"]:
                dir_num = struct.unpack(">I", self._root[
                        index + constants.FILENAME_LENGTH:
                        index + constants.FILENAME_LENGTH + 4 # size of dir_num in bytes
                    ])[0]
                break
            index += constants.ROOT_ENTRY_SIZE
        if dir_num is None:
            raise util.HTTPError(500, "Internal Error", "file %s not found" % request_context["filename"])

        # delete entry, turn off directory block bit in bitmap and request directory block
        self._bitmap[dir_num] = chr(0)
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = bytearray(constants.ROOT_ENTRY_SIZE)
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._after_dir_block
        util.init_client(
            request_context,
            client_action=constants.READ, 
            client_block_num=dir_num,
        )

    def _after_dir_block(
        self,
        request_context,
    ):
        (self._dir_block, request_context["block"]) = (request_context["block"], "")
        # go over dir_block and turn off all corresponding bits in bitmap
        index = 0
        while index < len(self._dir_block):
            block_num = struct.unpack(">I", self._dir_block[index:index+4])[0]
            if block_num == 0:
                break
            self._bitmap[block_num] = chr(0)
            index += 4

        self._update_disk(request_context)

    def _update_disk(
        self,
        request_context,
    ):
        request_context["state"] = constants.SLEEPING
        if self._bitmap and self._root:
            request_context["block"] = self._bitmap
            util.init_client(
                request_context,
                client_action=constants.WRITE, 
                client_block_num = 0,
            )
            request_context["block"] = self._root
            util.init_client(
                request_context,
                client_action=constants.WRITE, 
                client_block_num = 1,
            )

    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = "file %s was deleted successfully" % request_context["filename"]
        request_context["response"] += constants.BACK_TO_LIST
        request_context["response"] = util.text_to_html(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(DeleteService, self).before_response_headers(request_context)
