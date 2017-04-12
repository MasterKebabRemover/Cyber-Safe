class Pollable(object):
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

    def on_idle(self):
        return