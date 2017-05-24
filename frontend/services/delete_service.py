
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
            raise util.HTTPError(500, "Internal Error", util.text_to_css(
                "File name missing", error=True))
        request_context["filename"] = str(qs["filename"][0])
        self._parse_core(
            request_context,
            self._after_root,
        )

    def _after_root(
        self,
        request_context,
    ):
        request_context["block"] = ""

        # go over root and find file's entry, raise error if not found
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

        # delete entry, turn off directory block bit in bitmap and request
        # directory block
        self._bitmap = integration_util.bitmap_set_bit(
            self._bitmap,
            dir_num,
            0
        )
        entry.mark_empty() # mark entry as empty
        encrypted = entry.get_encrypted(
            user_key=encryption_util.sha(self._authorization)[:16],
        )
        self._file_size = encrypted["file_size"] # get file size for later use

        index -= constants.ROOT_ENTRY_SIZE
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = str(entry) # update directory root
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
        (self._main_block, request_context["block"]) = (
            request_context["block"], "")
        # go over main_block and turn off all corresponding bits in bitmap
        self._dir_block_list = []
        index = 0
        real_blocks = (self._file_size / (constants.BLOCK_SIZE**2)) + 1 # number of actual file blocks to delete
        while index < len(self._main_block):
            if index >= real_blocks: # means that we started deleting fake blocks
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
        real_blocks = (self._file_size / constants.BLOCK_SIZE) + 1 # marks actual file blocks to delete
        index = 0
        while index < len(self._dir_block):
            if index >= real_blocks: # means that we started deleting fake blocks
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

    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = "File deleted successfully"
        request_context["response"] = util.text_to_html(
            util.text_to_css(request_context["response"]))
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(DeleteService, self).before_response_headers(request_context)
