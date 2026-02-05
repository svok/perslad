import logging
import queue
import threading
from logging.handlers import QueueHandler, QueueListener


_log_queue = queue.Queue(maxsize=10000)
_listener: QueueListener | None = None


def start_logging_listener(handler: logging.Handler):
    global _listener

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    queue_handler = QueueHandler(_log_queue)
    root.addHandler(queue_handler)

    _listener = QueueListener(
        _log_queue,
        handler,
        respect_handler_level=True,
    )
    _listener.start()


def stop_logging_listener():
    global _listener
    if _listener:
        _listener.stop()
        _listener = None
