#!/usr/bin/python
import struct
import logging
import urlparse

import pyaes

import constants
import util
import encryption_util
from util import HTTPError
from root_entry import RootEntry
from service_base import ServiceBase
import block_util


class Download(ServiceBase):
    @staticmethod
    def name():
        return "/download"

    def before_request_content(
        self,
        request_context,
    ):
        self._authorization = self.get_authorization(request_context)
        qs = urlparse.parse_qs(request_context["parsed"].query)
        if not qs.get("filename"):
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise util.HTTPError(500, "Internal Error", util.text_to_css(
                "File name missing", error=True))
        request_context["file_name"] = str(qs["filename"][0])
        block_util.bd_action(
            request_context=request_context,
            block_num=0,
            action=constants.READ,
            service_wake_up=self._after_init,
        )

    def _after_init(
        self,
        request_context,
    ):
        init = bytearray(request_context["block"])
        if init[:len(constants.INIT_SIGNATURE)] != constants.INIT_SIGNATURE:
            raise util.HTTPError(500, "Internal Error", "Disk not initialized")
        index = len(constants.INIT_SIGNATURE)
        self._bitmaps = struct.unpack(">B", init[index:index+1])[0]
        self._dir_roots = struct.unpack(">B", init[index+1:index+2])[0]
        self._current_root = self._bitmaps + 1
        self._root = bytearray(0)
        block_util.bd_action(
            request_context=request_context,
            block_num=self._current_root,
            action=constants.READ,
            service_wake_up=self._construct_root,
        )

    def _construct_root(
        self,
        request_context,
    ):
        self._current_root += 1
        self._root += request_context["block"]
        if self._current_root <= self._dir_roots + self._bitmaps:
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_root,
                action=constants.READ,
                service_wake_up=self._construct_root,
            )
        else:
            self._after_root(request_context)

    def _after_root(
        self,
        request_context,
    ):
        index = 0
        main_num = None
        while index < len(self._root):
            # check if entry is the file
            entry = RootEntry()
            entry.load_entry(
                self._root[
                    index: index + constants.ROOT_ENTRY_SIZE
                ],
            )
            index += constants.ROOT_ENTRY_SIZE
            if entry.is_empty():
                continue
            if entry.compare_sha(
                user_key=encryption_util.sha(self._authorization)[:16],
                file_name=request_context["file_name"]
            ):
                main_num = entry.main_block_num
                encrypted = entry.get_encrypted(
                    user_key=encryption_util.sha(self._authorization)[:16],
                )
                request_context["headers"][constants.CONTENT_LENGTH] = encrypted["file_size"]
                break
        if main_num is None:
            raise HTTPError(
                500,
                "Internal Error",
                "File %s does not exist" %
                request_context["file_name"])
        block_util.bd_action(
            request_context=request_context,
            block_num=main_num,
            action=constants.READ,
            service_wake_up=self._handle_main_block,
        )

    def _handle_main_block(
        self,
        request_context,
    ):
        self._main_block = request_context["block"]
        self._main_index = 0
        self._dir_index = 0
        self._dir_block = None

    def _handle_dir_block(
        self,
        request_context,
    ):
        self._dir_block = request_context["block"]
        self._dir_index = 0

    def _handle_block(
        self,
        request_context,
    ):
        # decrypt block using user key
        iv = request_context["block"][:16]
        request_context["block"] = request_context["block"][16:]
        key = encryption_util.sha(self._authorization)[:16]
        aes = pyaes.AESModeOfOperationCBC(key, iv=str(iv))
        request_context["block"] = encryption_util.decrypt_block_aes(
            block=request_context["block"],
            aes=aes,
        )
        # send block to user
        request_context["response"] = request_context["block"]
        request_context["block"] = ""

    def before_response_headers(
        self,
        request_context,
    ):
        file_type = request_context["file_name"].split(".")
        if len(file_type) == 1:
            file_type.append("*")
        request_context["headers"][constants.CONTENT_TYPE] = constants.MIME_MAPPING.get(
            file_type[1], constants.MIME_MAPPING["*"], )
        request_context["headers"]["Content-Disposition"] = (
            "attachment; filename=%s" % request_context["file_name"]
        )

    def _next_dir_block(
        self,
        request_context,
    ):
        current_block_num = struct.unpack(
            ">I",
            self._main_block[self._main_index: self._main_index + 4]
        )[0]
        self._main_index += 4
        if current_block_num == 0:
            return None
        block_util.bd_action(
            request_context=request_context,
            block_num=current_block_num,
            action=constants.READ,
            service_wake_up=self._handle_dir_block,
        )
        return current_block_num

    def response(
        self,
        request_context,
    ):
        if self._main_index >= constants.BLOCK_SIZE:
            return None
        if self._dir_block is None or self._dir_index >= len(self._dir_block):
            # get next dir_block
            if not self._next_dir_block(request_context):
                return None
            return constants.RETURN_AND_WAIT
        else:
            current_block_num = struct.unpack(
                ">I",
                self._dir_block[self._dir_index: self._dir_index + 4],
            )[0]
            if current_block_num == 0:
                if not self._next_dir_block(request_context):
                    return None
                return constants.RETURN_AND_WAIT
            block_util.bd_action(
                request_context=request_context,
                block_num=current_block_num,
                action=constants.READ,
                service_wake_up=self._handle_block,
            )
            self._dir_index += 4
            return constants.RETURN_AND_WAIT
