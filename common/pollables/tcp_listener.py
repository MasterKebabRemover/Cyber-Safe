## @package cyber-safe.common.pollables.tcp_listener
# Class of TCP listener object, which listens for new connections and adds them to poller.
import socket
import logging

from common import constants
from common.pollables.pollable import Pollable

## TCP Listener
# pollable class which listens for new connections.
class TCPListener(Pollable):
    request_context = {
        "state": constants.LISTENER,
        "recv_buffer": "",
        "send_buffer": "",
    }

    ## Constructor
    # @param bind_address (str) bind address.
    # @param bind_port (int) bind port.
    # @param initiate (class) class to create after receiving new connection.
    # @param app_context (dict) application context.
    # @param fd_dict (dict) dictionary containing all current pollables
    #
    def __init__(
        self,
        bind_address,
        bind_port,
        initiate,
        app_context,
        fd_dict,
    ):
        self._initiate = initiate
        self._app_context = app_context
        self._fd_dict = fd_dict

        self.fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fd.bind((bind_address, bind_port))
        self.fd.listen(app_context["max_connections"])
        self.fd.setblocking(False)

    ## On read
    # reads new connection.
    # creates pollable class to handle that connection, adds it to general fd dict.
    def on_read(
        self,
    ):
        client, addr = self.fd.accept()
        self._fd_dict[client.fileno()] = self._initiate(
            socket=client,
            state=constants.ACTIVE,
            app_context=self._app_context,
            fd_dict=self._fd_dict
        )

    def on_write(self):
        pass

    ## On error
    # sets own state to closing.
    def on_error(self):
        self.request_context["state"] = constants.CLOSING

    def on_close(self):
        self.fd.shutdown(socket.SHUT_RD)

    def fileno(self):
        return self.fd.fileno()

    def on_idle(self):
        pass
