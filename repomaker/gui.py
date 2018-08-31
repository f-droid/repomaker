import logging
import subprocess
import time
from threading import Thread

import repomaker
import requests
import webview

URL = 'http://127.0.0.1:8000/'
WAIT_BEFORE_TASKS = 30  # number of seconds to wait before starting background tasks
logger = logging.getLogger(__name__)

# multi-thread access
task_process = None
terminate = False


def main():
    # start stuff in thread
    t_window = Thread(target=start)
    t_window.start()

    create_window()


def create_window():
    global terminate  # pylint: disable=global-statement
    try:
        webview.config["USE_QT"] = True  # use Qt instead of Gtk for webview
        webview.create_window("Repomaker", confirm_quit=True)
        terminate = True
    finally:
        # halt background tasks
        if task_process is not None:
            task_process.terminate()


def start():
    global task_process  # pylint: disable=global-statement
    # show loading screen
    webview.load_html(get_loading_screen())

    double_instance = server_started()
    if not double_instance:
        # start web server
        logger.debug("Starting server")
        t = Thread(target=repomaker.runserver)
        t.daemon = True
        t.start()

        # wait for server to start
        while not server_started():
            if not t.is_alive():
                logging.error('Repomaker webserver could not be started.')
                return
            time.sleep(0.1)

    # load repomaker into webview
    webview.load_url(URL)

    if not double_instance:
        # wait and then start the background tasks
        for i in range(0, WAIT_BEFORE_TASKS):
            if terminate:
                return
            time.sleep(1)
        if not terminate:
            # this needs to run as its own process
            task_process = subprocess.Popen(['repomaker-tasks'])


def get_loading_screen():
    return """
<body>
<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
<h1 style="font-size:500%;font-family:Roboto;">Loading...</h1>
</div>
</body>
    """


def server_started():
    try:
        return requests.head(URL).status_code == requests.codes.OK
    except Exception:
        return False
