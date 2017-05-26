## @package cyber-safe.frontend.services.download_service
#
# a service for file download from disk.
#
import struct
import logging
import urlparse

import pyaes

from common import constants
from common.utilities import util
from common.utilities import encryption_util
from common.utilities.util import HTTPError
from common.root_entry import RootEntry
from common.services.service_base import ServiceBase
from common.utilities import block_util

## File download class.
class Download(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    @staticmethod
    def name():
        return "/download"

    ## Function called before receiving HTTP content.
    #
    # gets user authorization and file name from query strings.
    # calls read bitmap and directory root from block device.
    #
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
        self._parse_core(
            request_context,
            self._after_root,
        )

    ## Function called after receiving directory root.
    #
    # searches root for file matching provided file name and user key.
    # raises and error if file not found.
    # if found calls read main block of file from block device.
    # also sets content length headers according to file size information from file entry.
    #
    def _after_root(
        self,
        request_context,
    ):
        index = 0
        main_num = None
        while index < len(self._root):
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
                self._file_size = encrypted["file_size"]
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

    ## Function called after receiving main block.
    # initializes variables for future use.
    def _handle_main_block(
        self,
        request_context,
    ):
        self._main_block = request_context["block"]
        self._main_index = 0
        self._dir_index = 0
        self._dir_block = None

    ## Function called before sending HTTP headers.
    #
    # sets headers according to file type.
    #
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

    ## Function called during sending HTTP content (file content).
    #
    # until finished reading file, reads one file block from block device at a time and calls handling functions to send it.
    # to read file data block, goes over directory block. if reached end of directory block, reads next one.
    #
    def response(
        self,
        request_context,
    ):
        if self._file_size == 0:
            return None
        if self._dir_block is None or self._dir_index >= len(self._dir_block):
            self._next_dir_block(request_context)
            return constants.RETURN_AND_WAIT
        else:
            current_block_num = struct.unpack(
                ">I",
                self._dir_block[self._dir_index: self._dir_index + 4],
            )[0]
            block_util.bd_action(
                request_context=request_context,
                block_num=current_block_num,
                action=constants.READ,
                service_wake_up=self._handle_block,
            )
            self._dir_index += 4
            return constants.RETURN_AND_WAIT

    ## Function called after reading file block.
    #
    # decrypts block by user key and sends it to user.
    #
    def _handle_block(
        self,
        request_context,
    ):
        iv = request_context["block"][:16]
        request_context["block"] = request_context["block"][16:]
        key = encryption_util.sha(self._authorization)[:16]
        aes = pyaes.AESModeOfOperationCBC(key, iv=str(iv))
        request_context["block"] = encryption_util.decrypt_block_aes(
            block=request_context["block"],
            aes=aes,
        )
        request_context["block"] = request_context["block"][:self._file_size]
        self._file_size -= len(request_context["block"])
        request_context["response"] = request_context["block"]
        request_context["block"] = ""

    ## Function used to read next directory block.
    #
    # this function is called if reading reaches end of a directory block.
    # looks in main block for next directory block index and reads it, then calls handling funcion.
    #
    def _next_dir_block(
        self,
        request_context,
    ):
        current_block_num = struct.unpack(
            ">I",
            self._main_block[self._main_index: self._main_index + 4]
        )[0]
        self._main_index += 4
        block_util.bd_action(
            request_context=request_context,
            block_num=current_block_num,
            action=constants.READ,
            service_wake_up=self._handle_dir_block,
        )
        return current_block_num

    ## Directory block handling function.
    # receives directory block and sets some reading variables.
    def _handle_dir_block(
        self,
        request_context,
    ):
        self._dir_block = request_context["block"]
        self._dir_index = 0
