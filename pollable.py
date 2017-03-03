class Pollable(object):
    request_context = {
        "recv_buffer": "",
        "send_buffer": "",
    }

    def on_read(self):
        return

    def on_write(self):
        return

    def on_error(self):
        return

    def on_close(self):
        return

    def fileno(self):
        return

    def on_receive(self):
        return