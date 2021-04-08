'''
Application entry point and main controller

poUIrup
Qianlang Chen
W 04/07/21
'''
from model import UI
from view import Icon, Indicator

VERSION = 'v4.2.0 (Beta) T 04/06/21'
TITLE = f'poUIrup\n{VERSION}'

is_suspended = False

def main():
    UI.start()
    Indicator.start_async()
    Icon.on_suspend_click = _on_icon_suspend
    Icon.on_exit_click = _on_icon_exit
    Icon.start(TITLE)

def suspend():
    global is_suspended
    is_suspended = not is_suspended
    Icon.change(is_suspended)
    Indicator.show((Indicator.SUSPEND_OFF, Indicator.SUSPEND_ON)[is_suspended])

def exit_app():
    # Stopping the event loop lifts the block and allows the system to
    # naturally exit
    Icon.stop()
    Indicator.stop()

def _on_icon_suspend():
    suspend()

def _on_icon_exit():
    exit_app()

if __name__ == '__main__':
    main()
