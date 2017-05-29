## @package frontend.services.delete_service
#
# a service for deletion of files from safe.
## @file delete_service.py Implementation of @ref frontend.services.delete_service
import logging
import struct
import urlparse

from common.utilities import block_util
from common import constants
from common.utilities import encryption_util
from common.utilities import util
from common.root_entry import RootEntry
from common.utilities import integration_util
from common.services.service_base import ServiceBase

## Delete service class.
class DeleteService(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    @staticmethod
    def name():
        return "/delete"

    ## Constructor.
    # initializes bitmap and root variables for future use.
    def __init__(
        self,
        request_context=None,
    ):
        self._bitmap = None
        self._root = None

    ## Function called before receiving HTTP content.
    #
    # checks validity of authorization and file name.
    # calls to read bitmap and root from block device.
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
        request_context["filename"] = str(qs["filename"][0])
        self._parse_core(
            request_context,
            self._after_root,
        )

    ## Function called after receiving bitmap and directory root.
    #
    # searches root for file matching provided file name and user key.
    # raises an error if file not found.
    # if found, deletes the entry, turns off corresponding bits in bitmap.
    # calls read file main block from block device.
    #
    def _after_root(
        self,
        request_context,
    ):
        request_context["block"] = ""

        index = 0
        dir_num = None
        while index < len(self._root):
            entry = RootEntry()
            entry.load_entry(
                self._root[index: index + constants.ROOT_ENTRY_SIZE]
            )
            index += constants.ROOT_ENTRY_SIZE
            if entry.is_empty():
                continue
            if entry.compare_sha(
                user_key=encryption_util.sha(self._authorization)[:16],
                file_name=request_context["filename"]
            ):
                dir_num = entry.main_block_num
                break
        if dir_num is None:
            raise util.HTTPError(500, "Internal Error", util.text_to_css(
                "file %s not found" % request_context["filename"], error=True))

        self._bitmap = integration_util.bitmap_set_bit(
            self._bitmap,
            dir_num,
            0
        )
        entry.mark_empty()
        encrypted = entry.get_encrypted(
            user_key=encryption_util.sha(self._authorization)[:16],
        )
        self._file_size = encrypted["file_size"]

        index -= constants.ROOT_ENTRY_SIZE
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = str(entry)
        block_util.bd_action(
            request_context=request_context,
            block_num=dir_num,
            action=constants.READ,
            service_wake_up=self._after_main_block,
        )

    ## Function called after receiving main block.
    #
    # to turn off all file bits in bitmap, creates a list of all directory blocks to read.
    # also turns of the bits relating to those blocks.
    #
    def _after_main_block(
        self,
        request_context,
    ):
        (self._main_block, request_context["block"]) = (
            request_context["block"], "")
        self._dir_block_list = []
        index = 0
        real_blocks = (self._file_size / (constants.BLOCK_SIZE**2)) + 1
        while index < len(self._main_block):
            if index >= real_blocks:
                break
            block_num = struct.unpack(
                ">I", self._main_block[index:index + 4])[0]
            if block_num == 0:
                break
            logging.debug(block_num)
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                block_num,
                0,
            )
            self._dir_block_list.append(block_num)
            index += 4
        self._delete_dir_blocks(request_context)

    ## Delete all file blocks through bitmap.
    # reads all directory blocks and calls handle_dir_block for each.
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

    ## Goes over the directory block, gets file block indices and turns of corresponding bits in bitmap.
    def _handle_dir_block(
        self,
        request_context,
    ):
        self._dir_block = request_context["block"]
        request_context["block"] = ""
        real_blocks = (self._file_size / constants.BLOCK_SIZE) + 1
        index = 0
        while index < len(self._dir_block):
            if index >= real_blocks:
                break
            block_num = struct.unpack(
                ">I", self._dir_block[index:index + 4])[0]
            if block_num == 0:
                break
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                block_num,
                0,
            )
            index += 4
        self._delete_dir_blocks(request_context)

    ## Update disk
    #
    # writes all altered blocks to block devices.
    #
    def _update_disk(
        self,
        request_context,
    ):
        self._current_bitmap = 1
        while self._bitmap:
            block = self._bitmap[:constants.BLOCK_SIZE]
            self._bitmap = self._bitmap[constants.BLOCK_SIZE:]
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_bitmap,
                action=constants.WRITE,
                block=block,
            )
            self._current_bitmap += 1

        self._current_root = self._bitmaps + 1
        while self._root:
            block = self._root[:constants.BLOCK_SIZE]
            self._root = self._root[constants.BLOCK_SIZE:]
            block_util.bd_action(
                request_context=request_context,
                block_num=self._current_root,
                action=constants.WRITE,
                block=block,
            )
            self._current_root += 1

    ## Function called before sending HTTP headers
    # sends the success message to client.
    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = "File deleted successfully"
        request_context["response"] = util.text_to_html(
            util.text_to_css(request_context["response"]))
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(DeleteService, self).before_response_headers(request_context)
