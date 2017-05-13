#!/usr/bin/python
import errno
import os
import tempfile
import logging
import socket
import struct
import urlparse

import block_util
import constants
import encryption_util
import util
from root_entry import RootEntry
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
        self._authorization = self.get_authorization(request_context)
        qs = urlparse.parse_qs(request_context["parsed"].query)
        if not qs.get("filename"):
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise util.HTTPError(500, "Internal Error", util.text_to_css("Filen name missing", error=True))
        request_context["filename"] = str(qs["filename"][0])
        block_util.bd_action(
            request_context=request_context,
            block_num=0,
            action=constants.READ,
            service_wake_up=self._after_bitmap,
        )

    def _after_bitmap(
        self,
        request_context,
    ):
        self._bitmap = bytearray(request_context["block"])
        block_util.bd_action(
            request_context=request_context,
            block_num=1,
            action=constants.READ,
            service_wake_up=self._after_root,
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
            entry = RootEntry()
            entry.load_entry(
                self._root[index: index + constants.ROOT_ENTRY_SIZE]
            )
            if entry.compare_sha(
                user_key=encryption_util.sha(self._authorization)[:16],
                file_name=request_context["filename"]
            ):
                dir_num = entry.main_block_num
                break
            index += constants.ROOT_ENTRY_SIZE
        if dir_num is None:
            raise util.HTTPError(500, "Internal Error", util.text_to_css("file %s not found" % request_context["filename"], error=True))

        # delete entry, turn off directory block bit in bitmap and request directory block
        self._bitmap = integration_util.bitmap_set_bit(
            self._bitmap,
            dir_num,
            0
        )
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = str(RootEntry())
        block_util.bd_action(
            request_context=request_context,
            block_num=dir_num,
            action=constants.READ,
            service_wake_up=self._after_main_block,
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
            block_util.bd_action(
                request_context=request_context,
                block_num=next_block,
                action=constants.READ,
                service_wake_up=self._handle_dir_block,
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
        if self._bitmap and self._root:
            block_util.bd_action(
                request_context=request_context,
                block_num=0,
                action=constants.WRITE,
                block=self._bitmap,
            )
            block_util.bd_action(
                request_context=request_context,
                block_num=1,
                action=constants.WRITE,
                block=self._root,
            )

    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = "File deleted successfully"
        request_context["response"] = util.text_to_html(util.text_to_css(request_context["response"]))
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(DeleteService, self).before_response_headers(request_context)
