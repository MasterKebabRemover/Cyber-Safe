## @package cyber-safe.common.pollables.http_client
# Class which handles HTTP state machine and client actions.
import errno
import socket
import logging
import traceback
import importlib

from client.services import *
from common import constants
from common.utilities import util
from common.services import service_base
from common.pollables.pollable import Pollable

## HTTP client.
# pollable class.
# handles HTTP client with state machine for request process.
class HttpClient(Pollable):

    ## Constructor.
    # @param socket (socket) socket.
    # @param state (int) self operation state.
    # @param app_context (dict) application context.
    # @param fd_dict (dict) dictionary of file descriptors.
    # @param action (str) action client should perform.
    # @param block_num (int) block which client has to read/write.
    # @param parent (Collable) parent server which initiated the client.
    # @param block (str) block to write in case of write service.
    def __init__(
        self,
        socket,
        state,
        app_context,
        fd_dict,
        action,
        block_num,
        parent,
        block=None
    ):
        self.request_context = {
            "code": None,
            "status": None,
            "req_headers": {},
            "headers": {},
            "content": "",
            "response": "",
            "recv_buffer": "",
            "send_buffer": "",
        }
        self.socket = socket
        self.request_context["state"] = state
        self._fd_dict = fd_dict
        self.request_context["app_context"] = app_context
        self.service_class = service_base.ServiceBase(self.request_context)
        self.request_context["action"] = action
        self.request_context["block_num"] = block_num
        self.request_context["parent"] = parent
        self.request_context["block"] = block

        REGISTRY = {
            service.name(): service for service in service_base.ServiceBase.__subclasses__()
        }

        try:
            self.service_class = REGISTRY[action](self.request_context)
        except KeyError:
            raise util.HTTPError(
                code=500,
                status="Internal Error",
                message="service not supported",
            )
        self._state_machine = self._get_state_machine()
        self._current_state = constants.SEND_STATUS_LINE

    ## Return own state machine.
    # state machine contains all http states and their corresponding functions.
    def _get_state_machine(
        self,
    ):
        return {
            constants.GET_FIRST_LINE: {
                "func": self._get_first_line,
                "next": constants.GET_HEADERS,
            },
            constants.GET_HEADERS: {
                "func": self._get_headers,
                "next": constants.GET_CONTENT,
            },
            constants.GET_CONTENT: {
                "func": self._get_content,
                "next": constants.TERMINATE,
            },
            constants.TERMINATE: {
                "func": self._terminate,
                "next": None
            },
            constants.SEND_STATUS_LINE: {
                "func": self._send_status_line,
                "next": constants.SEND_HEADERS,
            },
            constants.SEND_HEADERS: {
                "func": self._send_headers,
                "next": constants.SEND_RESPONSE,
            },
            constants.SEND_RESPONSE: {
                "func": self._send_response,
                "next": constants.GET_FIRST_LINE,
            },
        }

    ## On read.
    # called when there's data ready to be received, reads that data to own request context.
    def on_read(
        self,
    ):
        try:
            util.receive_buffer(self)
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error(e)
            util.add_status(self, code, e)
        self.on_idle()

    ## On idle.
    # @returns (bool) whether to call this function again or whether finished idle processes.
    # called by asynchronous loop to perform various idle operations in self service.
    # from this functon, the current state machine function is called.
    def on_idle(
        self,
    ):
        call_again = None
        try:
            call_again = self._state_machine[self._current_state]["func"]()
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error(e)
            util.add_status(self, code, e)
            self.request_context["response"] = e.message
            self.service_class = service_base.ServiceBase(self.request_context)

        if call_again is None:
            call_again = True
        return call_again

    # On write.
    # called by asynchronous server when there's data ready to be written.
    # writes ready data from own request context to socket.
    def on_write(
        self,
    ):
        try:
            while self.request_context["send_buffer"]:
                self.request_context["send_buffer"] = self.request_context["send_buffer"][
                    self.socket.send(self.request_context["send_buffer"]):
                ]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise

    # On error.
    # called when error rises, sets own state to closing.
    # also wakes up parent with same error.
    def on_error(
        self,
        error=None,
    ):
        if error:
            self.request_context["parent"].on_finish(error=error)
        self.request_context["state"] = constants.CLOSING

    # On close.
    # called when ready to close, closes own socket.
    def on_close(
        self,
    ):
        self.socket.shutdown(socket.SHUT_RD)

    def fileno(self):
        return self.socket.fileno()

    ## Get first line.
    # function called when on HTTP receive status line state.
    # parses status line to check whether own request ended with success or error.
    # raises error if no success.
    def _get_first_line(
        self,
    ):
        req, self.request_context["recv_buffer"] = util.recv_line(
            self.request_context["recv_buffer"])
        if not req:
            return False
        req_comps = req.split(" ", 2)
        if len(req_comps) != 3:
            raise RuntimeError("Incomplete HTTP protocol")
        if req_comps[0] != constants.HTTP_SIGNATURE:
            raise RuntimeError("Not HTTP protocol")

        if req_comps[1] != "200":
            raise util.HTTPError(
                req_comps[1],
                req_comps[2],
                message="",
            )
        self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_request_headers(self.request_context)

    ## Get headers.
    # function called when on HTTP get headers state.
    # uses util to get all headers, moves to next state when done.
    # returns false if not done receiving but no remaining buffer.
    def _get_headers(
        self,
    ):
        if util.get_headers(self.request_context):
            self.request_context["content_length"] = int(
                self.request_context["req_headers"].get(
                    constants.CONTENT_LENGTH, "0")
            )
            self.service_class.before_request_content(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]

    ## Get content.
    # called when on HTTP get content state.
    # receives available content, then passes it to service to operate.
    # according to command received from service, switches to next state or returns to wait for more data.
    def _get_content(
        self,
    ):
        service_command = None
        while True:
            service_command = self.service_class.handle_content(
                self.request_context)
            if service_command is not True:
                break

        if service_command is None:
            self.service_class.before_response_status(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]
            return True
        elif service_command is False:
            return False

    ## Send status line.
    # called when on HTTP send status line state.
    # sends HTTP request according to values initalized with.
    def _send_status_line(
        self,
    ):
        self.request_context["req_headers"] = self.service_class.get_header_dict(
        )
        self.service_class.before_response_status(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]

    ## Send headers.
    # called when in HTTP send headers state.
    # uses util to send all pending headers, switches to next state when done sending.
    def _send_headers(
        self,
    ):
        self.service_class.before_response_headers(self.request_context)
        if util.send_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
            self.service_class.before_response_content(self.request_context)

    ## Send response.
    # called when in HTTP response state.
    # calls service reponse send function.
    # sends all request data to server, then switches to next state.
    def _send_response(
        self,
    ):
        data = None
        data = self.service_class.response(self.request_context)
        if data is None:
            self._current_state = self._state_machine[self._current_state]["next"]
        else:
            self.request_context["send_buffer"] += data
            return True

    ## Terminate.
    # sets self state to closing.
    def _terminate(
        self,
    ):
        self.service_class.before_terminate(self.request_context)
        self.request_context["state"] = constants.CLOSING
        return False
