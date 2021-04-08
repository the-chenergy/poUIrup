'''
poUIrup
Qianlang Chen
W 04/07/21
'''
from pynput import keyboard, mouse
from typing import Tuple

class UI:
    '''Keyboard and mouse'''
    mouse_controller: mouse.Controller
    
    def start():
        UI.mouse_controller = mouse.Controller()
    
    def get_mouse_position() -> Tuple[int, int]:
        return UI.mouse_controller.position
