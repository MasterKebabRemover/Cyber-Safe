#!/usr/bin/python
import logging
import struct

import constants
import util
from service_base import ServiceBase
from root_entry import RootEntry
import encryption_util
import block_util

FORM_HEAD = """
    <head>
        <link rel="stylesheet" href="css/list.css">
    </head>
    <body>
    <center><h1>File List</h1></center>
    <div>
    <form>
    <table><tr>
    <th>File Name</th><th>File Size (Bytes)</th>
    </tr>
"""

FORM_ENTRY = """
    <tr class="hoverable"><td>
    <label>
    <input type="radio" class="radio" value="R1" name="filename" />
    R1
    </td>
    <td>R2</td>
    </label>
    </tr>
"""

FORM_ENDING = """
    </table>
    <br>
    <input type="submit" formaction="download" formmethod="get" value="Download" class="center">
    <br>
    <input type="submit" formaction="delete" formmethod="get" value="Delete" class="center">
    </form>
    <form action="fileupload" enctype="multipart/form-data" method="post">
    <input type="submit" value="Submit file">
    <input type="file" name="fileupload" id="browse", class="inputfile">
    <label for="browse"><img src="upload-icon.png" width=30 height=30></label>
    </form>
    </div>
    </body>
"""


class ListFiles(ServiceBase):
    @staticmethod
    def name():
        return "/list"

    def before_request_content(
        self,
        request_context,
    ):
        self._authorization = self.get_authorization(request_context)
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
        file_list = FORM_HEAD
        index = 0
        while index < len(self._root):
            entry = RootEntry()
            entry.load_entry(
                self._root[index: index + constants.ROOT_ENTRY_SIZE])
            index += constants.ROOT_ENTRY_SIZE
            if entry.is_empty():
                continue
            # extract file name and size from entry
            try:
                encrypted = entry.get_encrypted(
                    user_key=encryption_util.sha(self._authorization)[:16]
                )
            except Exception as e:  # means key does not fits, item does not belong to user
                continue
            # check if file belongs to user. if yes, list it.
            if entry.compare_sha(
                user_key=encryption_util.sha(self._authorization)[:16],
                file_name=encrypted["file_name"],
            ):
                file_list += FORM_ENTRY.replace(
                    "R1",
                    encrypted["file_name"],
                ).replace(
                    "R2",
                    str(encrypted["file_size"]),
                )
        file_list += FORM_ENDING
        request_context["response"] = util.text_to_html(file_list)

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = len(
            request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
