#!/usr/bin/python
import errno
import os
import tempfile
import logging
import socket
import struct

import constants
import util
from util import HTTPError
import integration_util
from service_base import ServiceBase
from http_client import HttpClient

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
        request_context["content_length"] -= 2 # for final boundary change

        request_context["req_headers"]["Content-Disposition"] = None
        request_context["req_headers"]["Content-Type"] = None

        request_context["response"] = "The files:\r\n"  # prepare reply in case of success

    def _handle_headers(
        self,
        request_context,
    ):
        line, request_context["recv_buffer"] = util.recv_line(request_context["recv_buffer"])
        while line is not None:
            request_context["content_length"] -= len(line)
            request_context["content_length"] -= 2 # for CRLF lost in util.recv_line
            if (line + "\r\n") == str(request_context["boundary"]):
                line, request_context["recv_buffer"] = util.recv_line(request_context["recv_buffer"])
                continue
            if line == "":
                self._current_state = self._state_machine[self._current_state]["next"]
                break
            else:
                line = util.parse_header(line)
                if line[0] in request_context["req_headers"]:
                    request_context["req_headers"][line[0]] = line[1]
                line, request_context["recv_buffer"] = util.recv_line(request_context["recv_buffer"])
        if len(request_context["recv_buffer"]) > constants.BLOCK_SIZE:
            raise RuntimeError("Maximum header size reached")

    def _init_file(
        self,
        request_context,
    ):
        cd = request_context["req_headers"]["Content-Disposition"].split("; ")
        request_context["filename"] = None
        request_context["fd"] = None
        for field in cd:
            if len(field.split("filename=")) == 2:
                request_context["filename"] = field.split("filename=")[1].strip("\"")
        if not request_context["filename"]:
            raise HTTPError(500, "Internal Error", "filename missing") 
        if len(request_context["filename"]) > 60:
            raise HTTPError(500, "Internal Error", "filename %s too long" % request_context["file_name"])
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
        # check that no files exist with same name
        # find place in bitmap for main block of new file:
        index = 0
        while index < len(self._bitmap*8):
            if integration_util.bitmap_get_bit(
                self._bitmap,
                index,
            ) == 1:
                index +=1
                continue
            self._bitmap = integration_util.bitmap_set_bit(
                self._bitmap,
                index,
                1,
            )
            break
        else:
            raise HTTPError(500, "Internal Error", "no room in disk")
        self._main_block_num = index

        # create entry for new file in dir root
        index = 0
        created = False
        while index < len(self._root):
            entry = util.parse_root_entry(self._root[index: index + constants.ROOT_ENTRY_SIZE])
            if entry["name"] != "":
                if entry["name"] == bytearray(request_context["filename"], 'utf-8'):
                    raise HTTPError(500, "Internal Error", "File %s already exists" % request_context["filename"])
            elif not created:
                created = True
                # save parameters to later create entry
                request_context["main_block_num"] = self._main_block_num
                request_context["dir_root_index"] = index
            index += constants.ROOT_ENTRY_SIZE
        if not created:
            raise HTTPError(500, "Internal Error", "no room in disk")
        # create main block for new file to later write to disk
        self._main_block = bytearray(constants.BLOCK_SIZE)
        self._dir_block = bytearray(constants.BLOCK_SIZE)
        self._main_index = 0
        self._dir_index = 0
        request_context["block"] = ""
        request_context["file_size"] = 0
        self._current_state = self._state_machine[self._current_state]["next"]

    def _write_file(
        self,
        request_context,
    ):
        if len(request_context["block"]) >= constants.BLOCK_SIZE:
            temp = request_context["block"][constants.BLOCK_SIZE:]
            request_context["block"] = request_context["block"][:constants.BLOCK_SIZE]
            self._write_block(request_context)
            request_context["block"] = temp
            return True

        index = request_context["recv_buffer"].find(request_context["boundary"])
        if index == 0:
            old_length = len(request_context["block"])
            request_context["block"] = util.ljust_00(request_context["block"], constants.BLOCK_SIZE)
            request_context["file_size"] -= (len(request_context["block"]) - old_length)
            self._write_block(request_context)
            self._current_state = self._state_machine[self._current_state]["next"]
            return True

        elif index == -1:
            data = request_context["recv_buffer"][:-len(request_context["boundary"])]
            request_context["block"] += data
            request_context["content_length"] -= len(data)
            request_context["recv_buffer"] = request_context["recv_buffer"][-len(request_context["boundary"]):]
            return False

        else:
            data = request_context["recv_buffer"][:index]
            request_context["block"] += data
            request_context["content_length"] -= len(data)
            request_context["recv_buffer"] = request_context["recv_buffer"][index:]
            return True

    def _write_block(
        self,
        request_context,
    ):
        if self._dir_index >= constants.BLOCK_SIZE:
            # reached end of dir_block, write it and get new one
            if self._main_index >= constants.BLOCK_SIZE:
                raise HTTPError(500, "Internal Error", "File %s too large" % request_context["file_name"])
            # save block to write for future
            request_context["future_block"] = request_context["block"]
            next_bitmap_index = self._next_bitmap_index()
            self._main_block[self._main_index: self._main_index + 4] = struct.pack(
                ">I",
                next_bitmap_index,
            )
            self._main_index += 4
            request_context["block"] = self._dir_block
            util.init_client(
                request_context,
                client_action=constants.WRITE, 
                client_block_num = next_bitmap_index,
            )
            self._dir_block = bytearray(constants.BLOCK_SIZE)
            self._dir_index = 0
            # get the data block back
            request_context["block"] = request_context["future_block"]
            request_context["future_block"] = ""

        request_context["file_size"] += constants.BLOCK_SIZE

        next_bitmap_index = self._next_bitmap_index()
        #also mark new block in dir block
        self._dir_block[self._dir_index: self._dir_index + 4] = struct.pack(
            ">I",
            next_bitmap_index,
        )
        self._dir_index += 4
        #write data to new block
        request_context["state"] = constants.SLEEPING
        util.init_client(
            request_context,
            client_action=constants.WRITE, 
            client_block_num = next_bitmap_index,
        )

    def _update_disk(
        self,
        request_context,
    ):
        # create root entry for file using data saved and calculated
        new_entry = util.create_root_entry({
            "name": request_context["filename"],
            "size": request_context["file_size"],
            "main_block": request_context["main_block_num"],
        })
        index = request_context["dir_root_index"]
        self._root[index: index + constants.ROOT_ENTRY_SIZE] = new_entry

        # write last dir block and mark it in main block
        if self._main_index >= constants.BLOCK_SIZE:
            raise HTTPError(500, "Internal Error", "File %s too large" % request_context["file_name"])
        next_bitmap_index = self._next_bitmap_index()
        request_context["block"] = self._dir_block
        request_context["state"] = constants.SLEEPING
        util.init_client(
            request_context,
            client_action=constants.WRITE, 
            client_block_num = next_bitmap_index,
        )
        self._main_block[self._main_index: self._main_index + 4] = struct.pack(
            ">I",
            next_bitmap_index,
        )

        request_context["block"] = self._main_block
        util.init_client(
            request_context,
            client_action=constants.WRITE, 
            client_block_num = self._main_block_num,
        )
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
        request_context["response"] += "%s\r\n" % (request_context["filename"])
        request_context["recv_buffer"] = request_context["recv_buffer"][len(request_context["boundary"]):]
        request_context["content_length"] -= len(request_context["boundary"])
        self._current_state = self._state_machine[self._current_state]["next"]
        
    def handle_content(
        self,
        request_context,
    ):
        request_context["recv_buffer"] = request_context["recv_buffer"].replace(
            request_context["final_boundary"],
            request_context["boundary"],
        )
        # logging.debug("------------------------")
        # logging.debug(self._current_state)
        while self._state_machine[self._current_state]["func"](
            request_context,
        ):
            pass

        if request_context["content_length"] <= 0:
            return

        # logging.debug(self._current_state)
        if request_context["state"] == constants.SLEEPING:
            return False

        if request_context["recv_buffer"][:-len(request_context["boundary"])]:
            return True
        return False

    def before_response_headers(
        self,
        request_context,
    ):
        if request_context["code"] == 200:
            request_context["response"] += "Were uploaded successfully"
        request_context["response"] += constants.BACK_TO_LIST
        request_context["response"] = util.text_to_html(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(FileUploadService, self).before_response_headers(request_context)

    def get_header_dict(
        self,
    ):
        return (
            {
                constants.CONTENT_LENGTH:0,
                constants.CONTENT_TYPE:None,
            }
        )

    def _next_bitmap_index(
        self,
    ):
        index = 0
        while index < len(self._bitmap*8):
            if integration_util.bitmap_get_bit(
                self._bitmap,
                index
            ) == 1:
                index +=1
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
