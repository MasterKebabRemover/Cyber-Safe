## @package common.pollables.http_socket
# Class which handles HTTP state machine and server actions.
## @file http_socket.py Implementation of @ref common.pollables.http_socket
import errno
import socket
import logging
import urlparse
import traceback
import importlib

from common import constants
from common.utilities import util
from common.services import service_base
from common.pollables.pollable import Pollable
from common.pollables.collable import Collable

## HTTP Socket.
# pollable and callable class.
# handles HTTP server with state machine for request process.
class HttpSocket(Pollable, Collable):

    ## Constructor.
    # @param socket (socket) socket.
    # @param state (int) self operation state.
    # @param app_context (dict) application context.
    # @param fd_dict (dict) dictionary of file descriptors.
    # @param service_class (class) class of self HTTP service.
    def __init__(
        self,
        socket,
        state,
        app_context,
        fd_dict,
        service_class=service_base.ServiceBase()
    ):
        self.request_context = {
            "code": 200,
            "status": "OK",
            "req_headers": {},
            "headers": {},
            "accounts": {},
            "content": "",
            "response": "",
            "recv_buffer": "",
            "send_buffer": "",
        }
        self.socket = socket
        self.request_context["state"] = state
        self.request_context["fd_dict"] = fd_dict
        self.request_context["app_context"] = app_context
        self.request_context["callable"] = self
        self.service_class = service_class
        for service in constants.MODULE_DICT[app_context["block_device"]]:
            importlib.import_module(service)

        self._state_machine = self._get_state_machine()
        self._current_state = constants.GET_FIRST_LINE

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
                "next": constants.SEND_STATUS_LINE,
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
                "next": constants.TERMINATE,
            },
            constants.TERMINATE: {
                "func": self._terminate,
                "next": None,
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
            self.on_error()
            util.add_status(self, code, e)

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
            self.on_error()
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
            if e.errno == errno.EPIPE:
                self.request_context["send_buffer"] = ""
        except Exception as e:
            traceback.print_exc()
            self.on_error
            self.service_class = service_base.ServiceBase(self.request_context)

    # On error.
    # called when error rises, sets own state to closing.
    def on_error(
        self,
    ):
        self.request_context["state"] = constants.CLOSING

    # On close.
    # called when ready to close, closes own socket.
    def on_close(
        self,
    ):
        self.socket.shutdown(socket.SHUT_WR)
        pass

    # On finish.
    # @param block (int) block of data received.
    # @param error (str) error occured during sleep time.
    #
    # Called by own client to wake up the HTTP socket after client finished it's work.
    #
    def on_finish(
        self,
        block="",
        error=None,
    ):
        self.request_context["state"] = constants.ACTIVE
        self.request_context["block"] = block
        try:
            if error:
                raise RuntimeError(str(error))
            wake_up_function = self.request_context.get("wake_up_function")
            self.request_context["wake_up_function"] = None
            if wake_up_function:
                wake_up_function(self.request_context)
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error()
            util.add_status(self, code, e)
            self.request_context["response"] = e.message
            self.service_class = service_base.ServiceBase(self.request_context)

    def fileno(self):
        return self.socket.fileno()

    ## Get first line.
    # function called when on HTTP receive status line state.
    # parses status line and creates matching service to handle rest of the request.
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
        if req_comps[2] != constants.HTTP_SIGNATURE:
            raise RuntimeError("Not HTTP protocol")

        method, uri, signature = req_comps
        if method not in constants.SUPPORTED_METHODS:
            raise RuntimeError(
                "HTTP unsupported method '%s'" % method,
            )
        if not uri or uri[0] != '/' or '\\' in uri:
            raise RuntimeError("Invalid URI")

        self.request_context["uri"] = uri
        self.request_context["parsed"] = urlparse.urlparse(uri)

        logging.debug(
            "fd %d called method %s" % (
                self.fileno(),
                self.request_context["parsed"].path
            )
        )

        REGISTRY = {
            service.name(): service for service in service_base.ServiceBase.__subclasses__()
        }
        self.service_class = REGISTRY.get(
            self.request_context["parsed"].path,
            REGISTRY.get("*"),
        )(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_request_headers(self.request_context)
        self.request_context["req_headers"] = self.service_class.get_header_dict(
        )

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
            self._current_state = self._state_machine[self._current_state]["next"]
            self.service_class.before_request_content(self.request_context)
        else:
            return False

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
    # sends status line according to data in request context.
    def _send_status_line(
        self,
    ):
        self.request_context["send_buffer"] += ((
            "%s %s %s\r\n"
        ) % (
            constants.HTTP_SIGNATURE,
            self.request_context["code"],
            self.request_context["status"],
        )
        ).encode("utf-8")
        self.request_context["status_sent"] = True
        self.service_class.before_response_headers(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]

    ## Send headers.
    # called when in HTTP send headers state.
    # uses util to send all pending headers, switches to next state when done sending.
    def _send_headers(
        self,
    ):
        if util.send_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_response_content(self.request_context)

    ## Send response.
    # called when in HTTP response state.
    # calls service reponse send function.
    # according to command received from service, either switches to next state, calls service again or
    # returns to asynchronous poller to sleep and wait for client actions.
    def _send_response(
        self,
    ):
        service_command = self.service_class.response(self.request_context)
        if self.request_context["response"]:
            self.request_context["send_buffer"] += self.request_context["response"]
            self.request_context["response"] = ""
        if service_command is None:
            service_command = constants.MOVE_TO_NEXT_STATE

        if service_command == constants.MOVE_TO_NEXT_STATE:
            self.service_class.before_terminate(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]

        elif service_command == constants.RETURN_AND_WAIT:
            return False

        elif service_command == constants.CALL_SERVICE_AGAIN:
            return True

    ## Terminate.
    # sets self state to closing.
    def _terminate(
        self,
    ):
        self.service_class.before_terminate(self.request_context)
        self.request_context["state"] = constants.CLOSING
        return False
