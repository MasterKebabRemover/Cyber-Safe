#!/usr/bin/python
import errno
import os
import socket
import struct
import logging

import constants
import util
from util import HTTPError
from service_base import ServiceBase
from http_client import HttpClient

class FileService(ServiceBase):
    @staticmethod
    def name():
        return "*"

    def __init__(
        self,
    ):
        super(FileService, self).__init__()
        self._dir_block = None
        self._dir_index = 0

    def before_request_headers(
        self,
        request_context,
    ):
        self._before_root(request_context)

    def _before_root(
        self,
        request_context,
    ):
        request_context["file_name"] = str(request_context["uri"][1:]) # remove the '/'
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._before_dir
        util.init_client(
            request_context,
            client_action=constants.READ, 
            client_block_num=1,
        )

    def _before_dir(
        self,
        request_context,
    ):
        directory_root = request_context["block"]
        index = 0
        dir_num = None
        while index < constants.BLOCK_SIZE:
            current_name = bytearray(directory_root[index:index + constants.FILENAME_LENGTH])
            current_name = current_name.rstrip('\x00')
            if current_name == "":
                index += constants.ROOT_ENTRY_SIZE
                continue
            if (
                current_name != request_context["file_name"]
            ):
                index += constants.ROOT_ENTRY_SIZE
            else:
                dir_num = struct.unpack(">I", directory_root[
                    index + constants.FILENAME_LENGTH:
                    index + constants.FILENAME_LENGTH + 4 # size of dir_num in bytes
                ])[0]
                break
        # logging.debug(current_name)
        # logging.debug(dir_num)
        if dir_num is None:
            raise HTTPError(500, "Internal Error", "File %s does not exist" % request_context["file_name"])
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._handle_dir_block
        util.init_client(
            request_context,
            client_action=constants.READ,
            client_block_num=dir_num,
        )

    def _handle_dir_block(
        self,
        request_context,
    ):
        self._dir_block = request_context["block"]
        blocks_in_file = 0
        index = 0
        while index < len(self._dir_block):
            dir_num = struct.unpack(">I", self._dir_block[
                    index: index+4 # size of dir_num in bytes
                ])[0]
            if dir_num != 0:
                blocks_in_file += 1
            index += 4
        request_context["headers"][constants.CONTENT_LENGTH] = blocks_in_file*constants.BLOCK_SIZE

    def _handle_block(
        self,
        request_context,
    ):
        request_context["response"] = request_context["block"]
            
    def response(
        self,
        request_context,
    ):
        if self._dir_block is None:
            return None
        if self._dir_index >= constants.BLOCK_SIZE:
            return None
        current_block_num = struct.unpack(
                ">I",
                self._dir_block[self._dir_index: self._dir_index + 4],
            )[0]
        if current_block_num == 0:
            return None
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._handle_block
        util.init_client(
            request_context,
            client_action=constants.READ,
            client_block_num=current_block_num,
        )
        self._dir_index += 4
        return constants.RETURN_AND_WAIT
