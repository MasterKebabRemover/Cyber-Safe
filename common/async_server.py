## @package cyber-safe.common.async_server
# Server for handling asynchronous I/O.
#
import errno
import logging
import select
import traceback

from common import constants
from common.pollables import http_socket
from common.pollables.tcp_listener import TCPListener

## Asynchronous Server.
#
# Handles events of all participating sockets.
#
class Server(object):

    ## Database of all participating sockets.
    _fd_dict = {}

    ## Whether to terminate server.
    _terminate = False

    ## Constructor.
    # @param app_context (dict) application context
    #
    def __init__(
        self,
        app_context,
    ):
        self._event_object = app_context["event_object"]
        self._timeout = app_context["timeout"]
        self._app_context = app_context

    ## Add listener.
    # create TCPListener object,
    # add it to fd dictionary.
    #
    def add_listener(
        self,
        bind_address,
        bind_port,
        initiate,
    ):
        listener = TCPListener(
            bind_address,
            bind_port,
            initiate,
            app_context=self._app_context,
            fd_dict=self._fd_dict,
        )
        self._fd_dict[listener.fileno()] = listener

    ## Stop server function.
    def stop(self, signum, frame):
        self._terminate = True

    ## Unregister an entry.
    # deletes entry from fd dict,
    # raises close flag on entry,
    # sets entry to closing state.
    #
    def _unregister(self, entry):
        logging.debug("Unregistered fd %s\n", entry.fileno())
        del self._fd_dict[entry.fileno()]
        entry.on_close()
        entry.request_context["state"] = constants.CLOSING

    ## Terminate the server.
    # enters close state for all sockets in database.
    #
    def terminate(self):
        logging.debug("Terminating")
        self._terminate = False
        for entry in self._fd_dict.values():
            entry.request_context["state"] = constants.CLOSING

    ## Create a new poller object.
    # @returns (dict) key - socket fd, value - event.
    # for each entry, decide it's mask according to the state and register in poller object.
    #
    def create_poller(self):
        poller = self._event_object()
        for entry in self._fd_dict.values():
            if entry.request_context["state"] == constants.SLEEPING:
                continue
            mask = select.POLLERR
            if (
                entry.request_context["send_buffer"]
            ):
                mask |= select.POLLOUT
            if (
                entry.request_context["state"] == constants.LISTENER or
                (
                    entry.request_context["state"] == constants.ACTIVE and
                    len(entry.request_context["recv_buffer"]
                        ) < constants.BLOCK_SIZE
                )
            ):
                mask |= select.POLLIN
            poller.register(
                entry.fileno(), mask
            )
        return poller

    ## Main loop - running server.
    def run(self):
        logging.debug("HTTP server running")
        while self._fd_dict:
            try:
                if self._terminate:
                    self.terminate()

                for entry in self._fd_dict.values():
                    if (
                        entry.request_context["state"] == constants.CLOSING and
                        not entry.request_context["send_buffer"]
                    ):
                        self._unregister(entry)

                for entry in self._fd_dict.values():
                    try:
                        while entry.request_context["state"] != constants.SLEEPING and entry.on_idle(
                        ):
                            pass
                    except Exception as e:
                        logging.error(traceback.format_exc())
                        self._unregister(entry)
                try:
                    for fd, flag in self.create_poller().poll(self._timeout):
                        entry = self._fd_dict[fd]
                        try:
                            if flag & (select.POLLHUP | select.POLLERR):
                                raise RuntimeError(
                                    "socket hung up or experienced error"
                                )
                            if flag & select.POLLIN:
                                entry.on_read()
                            if flag & select.POLLOUT:
                                entry.on_write()
                        except Exception as e:
                            logging.error(traceback.format_exc())
                            self._unregister(entry)
                except select.error as e:
                    if e[0] != errno.EINTR:
                        raise
            except Exception as e:
                logging.error(traceback.format_exc())
                self._terminate = True
        logging.debug("server terminated\n")
