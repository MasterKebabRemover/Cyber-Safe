
import os
import logging
import struct

import pyaes

from common import constants
from common.utilities import util
from common.utilities.util import HTTPError
from common.utilities import integration_util
from common.utilities import encryption_util
from common.root_entry import RootEntry
from common.services.service_base import ServiceBase
from common.utilities import block_util


class FileUploadService(ServiceBase):
    @staticmethod
    def name():
        return "/fileupload"

    def __init__(
        self,
        request_context,
    ):
        super(FileUploadService, self).__init__()
        [
            self._header_state,
            self._init_file_state,
            self._write_file_state,
            self._update_disk_state,
        ] = range(4)
        self._state_machine = {
            self._header_state: {
                "func": self._handle_headers,
                "next": self._init_file_state,
            },
            self._init_file_state: {
                "func": self._init_file,
                "next": self._write_file_state,
            },
            self._write_file_state: {
                "func": self._write_file,
                "next": self._update_disk_state,
            },
            self._update_disk_state: {
                "func": self._update_disk,
                "next": self._header_state,
            },
        }
        self._current_state = self._header_state
        self._bitmap = None
        self._root = None

    def before_request_content(
        self,
        request_context,
    ):
        self._authorization = self.get_authorization(request_context)
        super(FileUploadService, self).before_request_content(request_context)
        if request_context["req_headers"][constants.CONTENT_TYPE] is None:
            raise HTTPError(500, "Internal Error", "missing boundary header")
        request_context["boundary"] = "--"
        request_context["boundary"] += bytearray(
            request_context["req_headers"][constants.CONTENT_TYPE].split(
                "boundary="
            )[1].encode("utf-8")
        )
        request_context["final_boundary"] = request_context["boundary"] + "--"
        request_context["boundary"] += "\r\n"
        request_context["final_boundary"] += "\r\n"
        request_context["content_length"] -= 2  # for final boundary change

        request_context["req_headers"]["Content-Disposition"] = None
        request_context["req_headers"]["Content-Type"] = None

    def _handle_headers(
        self,
        request_context,
    ):
        line, request_context["recv_buffer"] = util.recv_line(
            request_context["recv_buffer"])
        while line is not None:
            request_context["content_length"] -= len(line)
            # for CRLF lost in util.recv_line
            request_context["content_length"] -= 2
            if (line + constants.CRLF) == str(request_context["boundary"]):
                line, request_context["recv_buffer"] = util.recv_line(
                    request_context["recv_buffer"])
                continue
            if line == "":
                self._current_state = self._state_machine[self._current_state]["next"]
                break
            else:
                line = util.parse_header(line)
                if line[0] in request_context["req_headers"]:
                    request_context["req_headers"][line[0]] = line[1]
                line, request_context["recv_buffer"] = util.recv_line(
                    request_context["recv_buffer"])
        if len(request_context["recv_buffer"]) > constants.BLOCK_SIZE:
            raise RuntimeError("Maximum header size reached")

    def _init_file(
        self,
        request_context,
    ):
        cd = request_context["req_headers"]["Content-Disposition"].split("; ")
        request_context["file_name"] = None
        request_context["fd"] = None
        for field in cd:
            if len(field.split("filename=")) == 2:
                request_context["file_name"] = field.split("filename=")[
                    1].strip("\"")
        if not request_context["file_name"]:
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise HTTPError(500, "Internal Error", util.text_to_css(
                "File name missing", error=True))
        if len(request_context["file_name"]) > 60:
            raise HTTPError(
                500, "Internal Error", "filename %s too long" %
                request_context["file_name"])
        self._parse_core(
            request_context,
            self._after_root
        )

    def _after_root(
        self,
        request_context,
    ):
        # check that no files exist with same name
        # find place in bitmap for main block of new file:
        self._main_block_num = self._next_bitmap_index()

        # create entry for new file in dir root
        index = 0
        created = False
        while index < len(self._root):
            entry = RootEntry()
            entry.load_entry(
                self._root[index: index + constants.ROOT_ENTRY_SIZE])
            if entry.is_empty():
                created = True
                # save parameters to later create entry
                request_context["main_block_num"] = self._main_block_num
                request_context["dir_root_index"] = index
            elif entry.compare_sha(
                user_key=encryption_util.sha(self._authorization)[:16],
                file_name=request_context["file_name"]
            ):
                raise HTTPError(
                    500, "Internal Error", util.text_to_css("File %s already exists" %
                    request_context["file_name"], error=True))
            index += constants.ROOT_ENTRY_SIZE
        if not created:
            raise HTTPError(500, "Internal Error", "no room in disk")
        # create main block for new file to later write to disk
        self._main_block = bytearray(0)
        self._dir_block = bytearray(0)
        self._main_index = 0
        self._dir_index = 0
        request_context["buffer"] = ""
        request_context["file_size"] = 0
        self._current_state = self._state_machine[self._current_state]["next"]

    def _write_file(
        self,
        request_context,
    ):
        # iv length
        if len(request_context["buffer"]
               ) >= constants.BLOCK_SIZE - constants.IV_LENGTH:
            self._write_block(
                request_context, request_context["buffer"][:constants.BLOCK_SIZE - constants.IV_LENGTH])
            request_context["buffer"] = request_context["buffer"][constants.BLOCK_SIZE -
                                                                  constants.IV_LENGTH:]
            return True

        index = request_context["recv_buffer"].find(
            request_context["boundary"])
        if index == 0:
            old_length = len(request_context["buffer"])
            request_context["buffer"] = util.random_pad(
                request_context["buffer"], constants.BLOCK_SIZE - constants.IV_LENGTH)
            request_context["file_size"] -= (
                len(request_context["buffer"]) - old_length)
            self._write_block(request_context, request_context["buffer"])
            self._current_state = self._state_machine[self._current_state]["next"]
            return True

        elif index == -1:
            data = request_context["recv_buffer"][:- \
                len(request_context["boundary"])]
            request_context["buffer"] += data
            request_context["content_length"] -= len(data)
            request_context["recv_buffer"] = request_context["recv_buffer"][-len(
                request_context["boundary"]):]
            return False

        else:
            data = request_context["recv_buffer"][:index]
            request_context["buffer"] += data
            request_context["content_length"] -= len(data)
            request_context["recv_buffer"] = request_context["recv_buffer"][index:]
            return True

    def _write_block(
        self,
        request_context,
        block,
    ):
        if self._dir_index >= constants.BLOCK_SIZE:
            # reached end of dir_block, write it and get new one
            if self._main_index >= constants.BLOCK_SIZE:
                raise HTTPError(
                    500, "Internal Error", "File %s too large" %
                    request_context["file_name"])
            # save block to write for future
            next_bitmap_index = self._next_bitmap_index()
            self._main_block += struct.pack(">I", next_bitmap_index, )
            self._main_index += 4
            block_util.bd_action(
                request_context=request_context,
                block_num=next_bitmap_index,
                action=constants.WRITE,
                block=self._dir_block,
            )
            self._dir_block = bytearray(0)
            self._dir_index = 0
            # get the data block back

        request_context["file_size"] += len(block)

        next_bitmap_index = self._next_bitmap_index()
        # also mark new block in dir block
        self._dir_block += struct.pack(
            ">I",
            next_bitmap_index,
        )
        self._dir_index += 4
        # encrypt data with user key and random iv. store iv in beginning of
        # data. iv is 16 bytes.
        iv = os.urandom(16)
        key = encryption_util.sha(self._authorization)[:16]
        aes = pyaes.AESModeOfOperationCBC(key, iv=iv)
        block = iv + encryption_util.encrypt_block_aes(
            block=block,
            aes=aes,
        )
        # write data to new block
        request_context["state"] = constants.SLEEPING
        block_util.bd_action(
            request_context=request_context,
            block_num=next_bitmap_index,
            action=constants.WRITE,
            block=block,
        )

    def _update_disk(
        self,
        request_context,
    ):
        # create root entry for file using data saved and calculated
        new_entry = RootEntry()
        new_entry.mark_full()
        new_entry.iv_size = 16
        new_entry.iv = os.urandom(16)
        new_entry.set_encrypted(
            user_key=encryption_util.sha(self._authorization)[:16],
            file_size=request_context["file_size"],
            file_name=request_context["file_name"],
        )
        new_entry.main_block_num = request_context["main_block_num"]
        new_entry.random = os.urandom(4)
        new_entry.sha = encryption_util.sha(
            new_entry.random,
            encryption_util.sha(self._authorization)[:16],  # user key
            request_context["file_name"],
        )[:16]
        index = request_context["dir_root_index"]
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = str(new_entry)

        # write last dir block and mark it in main block
        if self._main_index >= constants.BLOCK_SIZE:
            raise HTTPError(500, "Internal Error",
                            "File %s too large" % request_context["file_name"])
        next_bitmap_index = self._next_bitmap_index()
        request_context["state"] = constants.SLEEPING
        self._dir_block = util.random_pad(self._dir_block, constants.BLOCK_SIZE)
        block_util.bd_action(
            request_context=request_context,
            block_num=next_bitmap_index,
            action=constants.WRITE,
            block=self._dir_block,
        )
        self._main_block += struct.pack(
            ">I",
            next_bitmap_index,
        )
        self._main_block = util.random_pad(self._main_block, constants.BLOCK_SIZE)
        block_util.bd_action(
            request_context=request_context,
            block_num=self._main_block_num,
            action=constants.WRITE,
            block=self._main_block,
        )

        # write bitmap and root
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

        request_context["recv_buffer"] = request_context["recv_buffer"][len(
            request_context["boundary"]):]
        request_context["content_length"] -= len(request_context["boundary"])
        self._current_state = self._state_machine[self._current_state]["next"]

    def handle_content(
        self,
        request_context,
    ):
        request_context["recv_buffer"] = request_context["recv_buffer"].replace(
            request_context["final_boundary"], request_context["boundary"], )
        # logging.debug("------------------------")
        # logging.debug(self._current_state)
        if request_context["state"] == constants.SLEEPING:
            return False
        while self._state_machine[self._current_state]["func"](
            request_context,
        ):
            pass

        if request_context["content_length"] <= 0:
            return

        # logging.debug(self._current_state)

        if request_context["recv_buffer"][:-len(request_context["boundary"])]:
            return True
        return False

    def before_response_headers(
        self,
        request_context,
    ):
        if request_context["code"] == 200:
            request_context["response"] += "File uploaded successfully"
        request_context["response"] = util.text_to_html(
            util.text_to_css(request_context["response"]))
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(FileUploadService, self).before_response_headers(request_context)

    def get_header_dict(
        self,
    ):
        return (
            {
                constants.CONTENT_LENGTH: 0,
                constants.CONTENT_TYPE: None,
                "Cookie": None,
            }
        )

    def _next_bitmap_index(
        self,
    ):
        index = 0
        while index < len(self._bitmap * 8):
            if integration_util.bitmap_get_bit(
                self._bitmap,
                index
            ) == 1:
                index += 1
                continue
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                index,
                1
            )
            break
        if index == len(self._bitmap):
            raise HTTPError(500, "Internal Error", "no room in disk")
        return index
