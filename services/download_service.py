#!/usr/bin/python
import errno
import os
import socket
import struct
import logging
import urlparse

import constants
import util
from util import HTTPError
from service_base import ServiceBase
from http_client import HttpClient
import block_util

class Download(ServiceBase):
    @staticmethod
    def name():
        return "/download"

    def before_request_headers(
        self,
        request_context,
    ):
        self._before_root(request_context)

    def _before_root(
        self,
        request_context,
    ):
        qs = urlparse.parse_qs(request_context["parsed"].query)
        if not qs.get("filename"):
            raise util.HTTPError(500, "Internal Error", "file name missing")
        request_context["file_name"] = str(qs["filename"][0])
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
        directory_root = request_context["block"]
        index = 0
        main_num = None
        while index < constants.BLOCK_SIZE:
            entry = util.parse_root_entry(directory_root[
                index: index + constants.ROOT_ENTRY_SIZE
            ])
            if entry["name"] == "":
                index += constants.ROOT_ENTRY_SIZE
                continue
            if (
                entry["name"] != request_context["file_name"]
            ):
                index += constants.ROOT_ENTRY_SIZE
            else:
                main_num = entry["main_block"]
                request_context["headers"][constants.CONTENT_LENGTH] = entry["size"]
                break
        # logging.debug(current_name)
        # logging.debug(main_num)
        if main_num is None:
            raise HTTPError(500, "Internal Error", "File %s does not exist" % request_context["file_name"])
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
        request_context["response"] = request_context["block"]

    def before_response_headers(
        self,
        request_context,
    ):
        file_type = request_context["file_name"].split(".")
        if len(file_type) == 1:
            file_type.append("*")
        request_context["headers"][constants.CONTENT_TYPE] = constants.MIME_MAPPING.get(
            file_type[1],
            constants.MIME_MAPPING["*"],
        )
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
