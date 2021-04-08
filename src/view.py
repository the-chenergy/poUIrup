'''
poUIrup
Qianlang Chen
W 04/07/21
'''
from model import UI
import utils

from PIL import Image
import PySimpleGUI
import pystray
import screeninfo
from typing import Tuple

class Icon:
    '''System tray icon'''
    _IMAGES = (Image.open(utils.res_path('icon/default.ico')),
               Image.open(utils.res_path('icon/suspended.ico')))
    
    on_suspend_click = print
    on_exit_click = print
    
    _icon: pystray.Icon
    
    def start(title: str):
        '''Starts the system tray icon and blocks the thread.'''
        menu = pystray.Menu(
            pystray.MenuItem(
                'Suspend poUIrup',
                Icon.on_suspend_click,
                default=True,
            ),
            pystray.MenuItem('Exit poUIrup', Icon.on_exit_click),
        )
        Icon._icon = pystray.Icon('poUIrup', Icon._IMAGES[0], title, menu)
        Icon._icon.run()
    
    def change(is_suspended):
        Icon._icon.icon = Icon._IMAGES[is_suspended]
    
    def stop():
        '''Stops the system tray icon and unblocks the thread.'''
        Icon._icon.stop()

class Indicator:
    '''Pop-up indicator (for displaying caps-lock status, etc.)'''
    
    BRIGHTNESS = 'brightness'
    CAPS_LOCK_OFF = 'caps-lock-off'
    CAPS_LOCK_ON = 'caps-lock-on'
    FN_LOCK = 'fn-lock'
    IME_OFF = 'ime-off'
    IME_ON = 'ime-on'
    LEFTY_OFF = 'lefty-off'
    LEFTY_ON = 'lefty-on'
    LEFTY_ON = 'lefty-on'
    MUTE = 'mute'
    NEVER_SLEEP_OFF = 'never-sleep-off'
    NEVER_SLEEP_ON = 'never-sleep-on'
    NORMAL_SCROLLING_OFF = 'normal-scrolling-off'
    NORMAL_SCROLLING_ON = 'normal-scrolling-on'
    NUM_LOCK_OFF = 'num-lock-off'
    NUM_LOCK_ON = 'num-lock-on'
    OPACITY = 'opacity'
    PIN_OFF = 'pin-off'
    PIN_ON = 'pin-on'
    SMART_SWITCH_OFF = 'smart-switch-off'
    SMART_SWITCH_ON = 'smart-switch-on'
    SUSPEND_OFF = 'suspend-off'
    SUSPEND_ON = 'suspend-on'
    VOLUME_HIGH = 'volume-high'
    VOLUME_LOW = 'volume-low'
    VOLUME_MEDIUM = 'volume-medium'
    VOLUME_OFF = 'volume-off'
    
    _BACKGROUND_COLOR = '#202020'
    _IMAGE_PATH_FORMAT = utils.res_path('indicator/%s.png')
    _SIZE = (144, 144)
    _MARGIN = (36, 36)
    _REFRESH_INTERVAL = 25 / 864 * 1000
    _SHOW_DURATION = 36
    _FADE_DURATION = 6
    _TOTAL_DURATION = _SHOW_DURATION + _FADE_DURATION
    _SHOW_CLOSE_FLAG = -32
    
    on_click = print
    
    _window: PySimpleGUI.Window
    _image: PySimpleGUI.Image
    _show_time = -1
    _curr_image = None
    _next_image = None
    
    def start_async():
        '''Starts the indicator in background (invisible).'''
        Indicator._image = PySimpleGUI.Image(
            '',
            background_color=Indicator._BACKGROUND_COLOR,
            size=Indicator._SIZE,
        )
        Indicator._window = PySimpleGUI.Window(
            'poUIrup Indicator',
            ((Indicator._image,),),
            background_color=Indicator._BACKGROUND_COLOR,
            keep_on_top=True,
            no_titlebar=True,
            size=Indicator._SIZE,
        )
        Indicator._window.finalize()
        Indicator._window.hide()
    
    def show(image: str):
        '''
        Shows the indicator with a particular image (represented by string
        constants such as `Indicator.BRIGHTNESS`) and fades out automatically
        after a time period.
        '''
        Indicator._next_image = image
        # `Indicator._show_time` counts down from some number (number of total
        # frames) to zero. The first `_SHOW_DURATION` frames shows the
        # indicator persistently, and the last `_FADE_DURATION` frames linearly
        # fades the indicator out. According to PySimpleGUI's documentation,
        # Multiple processes/threads may induce bugs, so only one thread is
        # preserved to handle the animation.
        if Indicator._show_time >= 0:
            Indicator._show_time = Indicator._TOTAL_DURATION
            return
        Indicator._show_time = Indicator._TOTAL_DURATION
        Indicator._window.move(*Indicator._get_position())
        Indicator._window.un_hide()
        while Indicator._show_time >= 0:
            Indicator._window.read(Indicator._REFRESH_INTERVAL)
            Indicator._show_time -= 1
            Indicator._refresh()
        if Indicator._show_time <= Indicator._SHOW_CLOSE_FLAG:
            Indicator._window.close()
        else:
            Indicator._window.hide()
    
    def stop():
        if Indicator._show_time >= 0:
            # Animation running; let the animation thread handle close
            Indicator._show_time = Indicator._SHOW_CLOSE_FLAG
        else:
            Indicator._window.close()
    
    def _get_position() -> Tuple[float, float]:
        '''
        Default pop-up location: the top-right corner of the monitor that the
        mouse cursor is currently on.
        '''
        mouse_x, mouse_y = UI.get_mouse_position()
        for monitor in screeninfo.get_monitors():
            monitor_right = monitor.x + monitor.width
            monitor_bottom = monitor.y + monitor.height
            if (monitor.x <= mouse_x < monitor_right and
                    monitor.y <= mouse_y < monitor_bottom):
                return (monitor_right - Indicator._SIZE[0] -
                        Indicator._MARGIN[0], Indicator._MARGIN[1])
    
    def _refresh():
        if Indicator._show_time == Indicator._TOTAL_DURATION - 1:
            if Indicator._curr_image != Indicator._next_image:
                Indicator._curr_image = Indicator._next_image
                Indicator._image.update(Indicator._IMAGE_PATH_FORMAT %
                                        Indicator._curr_image)
            Indicator._window.set_alpha(1.)
            Indicator._window.move(*Indicator._get_position())
        elif Indicator._show_time < Indicator._FADE_DURATION:
            Indicator._window.set_alpha(Indicator._show_time /
                                        Indicator._FADE_DURATION)
        
        Indicator._window.refresh()
