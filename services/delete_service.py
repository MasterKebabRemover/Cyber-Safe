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
import integration_util
from service_base import ServiceBase
from http_client import HttpClient

class DeleteService(ServiceBase):
    @staticmethod
    def name():
        return "/delete"

    def __init__(
        self,
        request_context=None,
    ):
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
            entry = util.parse_root_entry(self._root[index: index + constants.ROOT_ENTRY_SIZE])
            if entry["name"] == request_context["filename"]:
                dir_num = entry["main_block"]
                break
            index += constants.ROOT_ENTRY_SIZE
        if dir_num is None:
            raise util.HTTPError(500, "Internal Error", "file %s not found" % request_context["filename"])

        # delete entry, turn off directory block bit in bitmap and request directory block
        self._bitmap = integration_util.bitmap_set_bit(
            self._bitmap,
            dir_num,
            0
        )
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = util.create_root_entry(
            {"clean_entry": True}
        )
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._after_main_block
        util.init_client(
            request_context,
            client_action=constants.READ, 
            client_block_num=dir_num,
        )

    def _after_main_block(
        self,
        request_context,
    ):
        (self._main_block, request_context["block"]) = (request_context["block"], "")
        # go over main_block and turn off all corresponding bits in bitmap
        self._dir_block_list = []
        index = 0
        while index < len(self._main_block):
            block_num = struct.unpack(">I", self._main_block[index:index+4])[0]
            if block_num == 0:
                break
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                block_num,
                0,
            )
            # save in order to go over all dir blocks
            self._dir_block_list.append(block_num)
            index += 4
        self._delete_dir_blocks(request_context)

    def _delete_dir_blocks(
        self,
        request_context,
    ):
        if not self._dir_block_list:
            self._update_disk(request_context)
        else:
            next_block = self._dir_block_list.pop()

            request_context["state"] = constants.SLEEPING
            request_context["wake_up_function"] = self._handle_dir_block
            util.init_client(
                request_context,
                client_action=constants.READ, 
                client_block_num=next_block,
            )

    def _handle_dir_block(
        self,
        request_context,
    ):
        self._dir_block = request_context["block"]
        request_context["block"] = ""
        self._delete_dir_block(request_context)

    def _delete_dir_block(
        self,
        request_context,
    ):
        # go over dir_block and turn off all data bits in bitmap
        index = 0
        while index < len(self._dir_block):
            block_num = struct.unpack(">I", self._dir_block[index:index+4])[0]
            if block_num == 0:
                break
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                block_num,
                0,
            )
            index += 4
        self._delete_dir_blocks(request_context)

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
