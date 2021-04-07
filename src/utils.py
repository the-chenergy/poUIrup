'''
Utility functions

poUIrup
Qianlang Chen
W 03/31/21
'''

import sys
from os import path

def res_path(filename: str) -> str:
    '''Returns the relative path to some resource file.'''
    try:
        # The secret place that PyInstaller stores (remaps) the application's
        # files
        prefix = sys._MEIPASS
    except AttributeError:
        prefix = ''
    return path.join(prefix, filename)
