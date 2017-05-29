## @package frontend.services.list_files_service
# a service to provide an HTML list with user's files on the disk.
## @file list_files_service.py Implementation of @ref frontend.services.list_files_service
import logging
import struct

from common import constants
from common.utilities import util
from common.services.service_base import ServiceBase
from common.root_entry import RootEntry
from common.utilities import encryption_util

## constant head of the HTML page.
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

## template for HTML file list entry. "R1" and "R2" are later replaced with file information.
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
## constnat ending of the HTML page.
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

## List files service class.
class ListFiles(ServiceBase):
    ## Class name function.
    # @returns (str) class name.
    @staticmethod
    def name():
        return "/list"

    ## Function called before sending HTTP content.
    # gets user authorization and calls read bitmaps and directory roots from block device.
    def before_request_content(
        self,
        request_context,
    ):
        self._authorization = self.get_authorization(request_context)
        self._parse_core(
            request_context,
            self._after_root,
        )

    ## Function called after receiving directory root and bitmap.
    # for each non-empty entry in directory root, try to decrypt it using user key.
    # if error is raised, means that key doesn't match, file does not belong to user and should not be listed.
    # if no error is raised, extract file name and add the file list entry for that file.
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
            try:
                encrypted = entry.get_encrypted(
                    user_key=encryption_util.sha(self._authorization)[:16]
                )
            except Exception as e:
                continue
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

    ## Function called before sending HTTP response headers.
    # sets the content length and content type headers to match sent content.
    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = len(
            request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
