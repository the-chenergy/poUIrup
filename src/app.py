'''
Application entry point and main controller

poUIrup
Qianlang Chen
T 04/06/21
'''

from model import Icon

VERSION = 'v4.2.0 (Beta) T 04/06/21'
TITLE = f'poUIrup\n{VERSION}'

def main():
    Icon.on_suspend_click = on_icon_suspend
    Icon.on_exit_click = on_icon_exit
    Icon.start(TITLE)

def on_icon_suspend():
    print('Toggling suspension...')

def on_icon_exit():
    # Stopping the event loop lifts the block and allows the system to
    # naturally exit.
    Icon.stop()

if __name__ == '__main__':
    main()
