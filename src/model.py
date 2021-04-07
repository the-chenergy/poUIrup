'''
Model

poUIrup
Qianlang Chen
T 04/06/21
'''

from PIL import Image
import pystray
from pystray import Menu, MenuItem
import utils

class Icon:
    '''Represents and controls the system tray icon.'''
    
    _DEFAULT_IMAGE_PATH = utils.res_path('res/default-icon.ico')
    
    on_suspend_click = print
    on_exit_click = print
    
    _icon: pystray.Icon
    
    def start(title: str):
        '''Starts the system tray icon and blocks the thread.'''
        image = Image.open(Icon._DEFAULT_IMAGE_PATH)
        menu = Menu(
            MenuItem('Suspend poUIrup', Icon.on_suspend_click, default=True),
            MenuItem('Exit poUIrup', Icon.on_exit_click),
        )
        Icon._icon = pystray.Icon('poUIrup', image, title, menu)
        Icon._icon.run()
    
    def stop():
        '''Stops the system tray icon and unblock the thread.'''
        Icon._icon.stop()
