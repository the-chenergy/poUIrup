'''
A cross-platform (Windows, Mac, Linux) attempt of the Asianboii's UI.

To debug: run from the project's root: `python src/app.py`

To build: run from the project's root: `pyinstaller app.spec -F`, executable 
built at `dist/app`

poUIrup v4.2
Qianlang Chen
A 05/01/21
'''

from os import path
import sys
import wx

class App:
    '''Application entry point.'''
    
    VERSION = 'v4.2.0b'
    TITLE = 'poUIrup ' + VERSION
    
    isSuspended = False
    
    _app: wx.App
    
    def start():
        App._app = wx.App()
        # Main thread: icon and indicator (required by wxPython)
        # 2nd thread: UI/keyboard
        # 3nd thread: UI/mouse
        Mouse.start()
        Keyboard.start()
        Indicator.start()
        Icon.start(App.TITLE)
        App._app.MainLoop()
    
    def resPath(filename: str) -> str:
        '''Returns the relative path to some resource file.'''
        try:
            # The secret place that PyInstaller stores (remaps) the
            # application's files
            prefix = sys._MEIPASS
        except AttributeError:
            prefix = ''
        return path.join(prefix, 'res', filename)
    
    def toggleSuspend():
        App.isSuspended = not App.isSuspended
        Icon.change(App.isSuspended)
        indicatorImage = ('suspend-off', 'suspend-on')[App.isSuspended]
        wx.CallAfter(Indicator.show, 'suspend', Indicator.SHOW_TIME_LONG,
                     indicatorImage)
    
    def stop():
        Keyboard.stop()
        Indicator.stop()
        Icon.stop()

from wx import adv

class Icon:
    '''System tray icon. (Also controls the lifetime of the indicator.)'''
    
    _title: str
    _taskBarIcon: adv.TaskBarIcon
    _icons: tuple[wx.Icon]
    _menu: wx.Menu
    _itemCallbacks: dict[int, object] = {}
    
    def start(title: str):
        '''
        Starts running the icon and indicator, blocking the thread.
        The indicator should be started before this call.
        
        Args:
            title (str): The text to display in the icon's tooltip.
        '''
        Icon._title = title
        Icon._menu = wx.Menu()
        Icon._createMenu()
        Icon._icons = (wx.Icon(App.resPath('icon/default.ico')),
                       wx.Icon(App.resPath('icon/suspended.ico')))
        Icon._taskBarIcon = adv.TaskBarIcon()
        Icon._taskBarIcon.Bind(adv.EVT_TASKBAR_CLICK, Icon._onIconClick)
        Icon._taskBarIcon.Bind(adv.EVT_TASKBAR_LEFT_DOWN,
                               lambda _: App.toggleSuspend())
        Icon.change(False)
    
    def change(isSuspended: bool):
        '''
        Changes the icon image to correlate to whether the application is
        currently suspended.
        
        Args:
            isSuspended (bool): Whether the application is currently suspended.
        '''
        Icon._taskBarIcon.SetIcon(Icon._icons[isSuspended],
                                  Icon._title + isSuspended * ' (suspended)')
    
    def showMenu():
        '''Forces the menu to show at the current mouse position.'''
        Icon._taskBarIcon.PopupMenu(Icon._menu)
    
    def stop():
        '''
        Stops running the icon and indicator. The indicator should be stopped
        before this call.
        '''
        Icon._taskBarIcon.Destroy()
    
    def _createMenu():
        Icon._appendMenu(wx.ID_STOP, 'Suspend poUIrup', App.toggleSuspend)
        Icon._appendMenu(wx.ID_EXIT, 'Exit poUIrup', App.stop)
        Icon._menu.Bind(wx.EVT_MENU, Icon._onIconMenu)
    
    def _appendMenu(id, text, callback):
        Icon._itemCallbacks[Icon._menu.Append(id, text).Id] = callback
    
    def _onIconClick(event):
        Icon.showMenu()
    
    def _onIconMenu(event):
        Icon._itemCallbacks[event.Id]()

import re
import screeninfo

class Indicator:
    '''Pop-up indicator (for displaying caps-lock status, etc.).'''
    
    SHOW_TIME_LONG = 36 # in number of refreshes
    SHOW_TIME_PERSISTENT = 1 << 30
    BAR_COLOR_GREEN = ''
    
    _BACKGROUND_COLOR = '#151515'
    _BAR_BACKGROUND_COLOR = '#000000'
    _CELL_WIDTH = 144
    _CELL_HEIGHT = 144
    _REFRESH_INTERVAL = 25000 / 144 / 6 # in ms
    _IMAGE_FILENAME_FORMAT = 'indicator/%s.png'
    _POSITIONS = ((1, -1, -36, 0, 0, 36), (0, 0, 36, 1, -1, -36))
    '''
    (parentWidthMult, childWidthMult, marginX, parentHeightMult,
    childHeightMult, marginY)
    
    Primary position: top right of the active monitor
    Secondary position: bottom left of the active monitor
    Click to toggle.
    '''
    _BAR_WIDTH = 108
    _BAR_HEIGHT = 12
    _BAR_POSITION = (.5, -.5, 0, 1, -1, -(_CELL_WIDTH - _BAR_WIDTH) / 2)
    
    _frame: wx.Frame
    _imageBitmapCache: dict[str, tuple[wx.Bitmap, str]] = {}
    '''imageKey -> (bitmap, brightestColor)'''
    _barBitmapCache: dict[str, wx.Bitmap] = {}
    '''color -> bitmap'''
    _cellWidgets: list[tuple[wx.StaticBitmap, wx.StaticBitmap, wx.StaticBitmap,
                             wx.StaticText]] = []
    '''cellIndex -> (imageWidget, barBackground, barForeground, textWidget)'''
    _shownCells: list[list[str, int, str, float, str]] = []
    '''
    cellIndex -> [cellKey, numRefreshesRemaining, imageKey, barValue, text]
    '''
    _isRunning = False
    _currPositionIndex = 0
    
    def start():
        '''
        Initializes the indicator. Call `Icon.start()` to start running both the
        icon and the indicator.
        '''
        Indicator._frame = wx.Frame(
            parent=None,
            size=(Indicator._CELL_WIDTH, Indicator._CELL_HEIGHT),
            style=(wx.FRAME_TOOL_WINDOW | wx.FRAME_NO_TASKBAR |
                   wx.FRAME_SHAPED | wx.STAY_ON_TOP))
        Indicator._frame.SetBackgroundColour(Indicator._BACKGROUND_COLOR)
        Indicator._frame.Bind(wx.EVT_LEFT_DOWN, Indicator._onFrameLeftDown)
        Indicator._frame.Bind(wx.EVT_RIGHT_DOWN, Indicator._onFrameRightDown)
        Indicator._isRunning = True
        wx.CallLater(Indicator._REFRESH_INTERVAL, Indicator._refresh)
    
    def show(cellKey: str,
             showTime: int,
             imageKey: str,
             barValue: float = None,
             text: str = None):
        '''
        Shows a new cell with an image and optionally a bar or text, or
        replaces an existing cell with the same `cellKey`.
        
        Args:
            cellKey (str): The cell's key.
            showTime (int): X refreshes (defined by `SHOW_TIME_*`) before
                automatically hiding the cell.
            imageKey (str): A filename in `res/indicator` without extension.
            barValue (float, optional): A value within [0, 1] or None to hide
                the bar. Defaults to None.
            text (str, optional): The text to display or None to hide the
                textbox. Defaults to None.
        '''
        for cell in Indicator._shownCells:
            if cell[0] == cellKey: break
        else:
            Indicator._shownCells.append([cellKey] + [None] * 4)
            cell = Indicator._shownCells[-1]
        cell[1] = showTime
        cell[2] = imageKey
        cell[3] = barValue
        cell[4] = text
        Indicator._updateCells()
        Indicator._updatePositionAndSize()
    
    def hide(cellKey: str):
        '''
        Hides the cell with the same `cellKey`, if there is any.
        
        Args:
            cellKey (str): The key of the cell to hide.
        '''
        for i in range(len(Indicator._shownCells)):
            if Indicator._shownCells[i][0] == cellKey:
                Indicator._shownCells.pop(i)
                Indicator._updateCells()
                Indicator._updatePositionAndSize()
                break
    
    def suspend():
        '''Applies the suspension status to the indicator.'''
        Indicator._updatePositionAndSize()
    
    def stop():
        '''
        Destroys the indicator. Call `Icon.stop()` to stop running both the icon
        and the indicator.
        '''
        Indicator._isRunning = False
        Indicator._frame.Close()
    
    def _getImageBitmapAndColor(imageKey):
        '''
        Returns the cached bitmap data and the theme color (of the brightest
        pixel in the bitmap) of the referred cell image.
        '''
        if imageKey not in Indicator._imageBitmapCache:
            bitmap = wx.Bitmap()
            bitmap.LoadFile(
                App.resPath(Indicator._IMAGE_FILENAME_FORMAT % imageKey))
            # Scan through the middle of the image horizontally to find the
            # brightest color (the highest V value in HSV), assuming that the
            # middle of any image is the most "representative."
            image: wx.Image = bitmap.ConvertToImage()
            brightestValue = -1
            y = image.Height // 2
            for x in range(image.Width):
                r = image.GetRed(x, y)
                g = image.GetGreen(x, y)
                b = image.GetBlue(x, y)
                value = wx.Image.RGBtoHSV(wx.Image.RGBValue(r, g, b)).value
                if value > brightestValue:
                    brightestValue = value
                    brightestColor = f'#{r:02x}{g:02x}{b:02x}'
            Indicator._imageBitmapCache[imageKey] = (bitmap, brightestColor)
        return Indicator._imageBitmapCache[imageKey]
    
    def _updateCells():
        '''Applies the data of currently-shown cells to the widgets.'''
        for i, cell in enumerate(Indicator._shownCells):
            # Create a new cell its widgets if needed.
            if i == len(Indicator._cellWidgets):
                imagePosition = (0, i * Indicator._CELL_HEIGHT)
                imageWidget = wx.StaticBitmap(parent=Indicator._frame,
                                              pos=imagePosition,
                                              size=(Indicator._CELL_WIDTH,
                                                    Indicator._CELL_HEIGHT))
                imageWidget.Bind(wx.EVT_LEFT_DOWN, Indicator._onFrameLeftDown)
                imageWidget.Bind(wx.EVT_RIGHT_DOWN, Indicator._onFrameRightDown)
                # The bar is made up from a background with a constant size and
                # color and a foreground with a changing size and the theme
                # color.
                # The bar and the text are both added as children of the image,
                # making it easier to calculate their positions.
                (frameWidthMult, barWidthMult, marginX, frameHeightMult,
                 barHeightMult, marginY) = Indicator._BAR_POSITION
                barPosition = (int(imagePosition[0] * 0 +
                                   frameWidthMult * Indicator._CELL_WIDTH +
                                   barWidthMult * Indicator._BAR_WIDTH +
                                   marginX),
                               int(imagePosition[1] * 0 +
                                   frameHeightMult * Indicator._CELL_HEIGHT +
                                   barHeightMult * Indicator._BAR_HEIGHT +
                                   marginY))
                barSize = (Indicator._BAR_WIDTH, Indicator._BAR_HEIGHT)
                barBackground = wx.StaticBitmap(parent=imageWidget,
                                                pos=barPosition,
                                                size=barSize)
                barBackground.SetBitmap(
                    Indicator._getBarBitmap(Indicator._BAR_BACKGROUND_COLOR))
                barForeground = wx.StaticBitmap(parent=barBackground,
                                                size=barSize)
                textWidget = wx.StaticText(parent=imageWidget,
                                           pos=barPosition,
                                           size=barSize,
                                           style=wx.ALIGN_CENTER)
                textWidget.SetFont(
                    wx.Font(Indicator._BAR_HEIGHT, wx.FONTFAMILY_DEFAULT,
                            wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                Indicator._cellWidgets.append(
                    (imageWidget, barBackground, barForeground, textWidget))
            # Apply the image, bar value, and text for cell i.
            (imageWidget, barBackground, barForeground,
             textWidget) = Indicator._cellWidgets[i]
            imageKey, barValue, text = cell[2:]
            bitmap, color = Indicator._getImageBitmapAndColor(imageKey)
            imageWidget.SetBitmap(bitmap)
            if barValue is not None:
                barBackground.Show()
                barForeground.SetBitmap(Indicator._getBarBitmap(color))
                barForeground.SetSize(barValue * Indicator._BAR_WIDTH,
                                      Indicator._BAR_HEIGHT)
            else:
                barBackground.Hide()
            if text is not None:
                textWidget.SetLabelText(text)
                textWidget.SetForegroundColour(color)
                textWidget.Show()
            else:
                textWidget.Hide()
    
    def _getBarBitmap(color):
        if color not in Indicator._barBitmapCache:
            # Parse "#rrggbb"
            r, g, b = (int(s, 16) for s in re.findall('..', color[1:]))
            bitmap = wx.Bitmap.FromRGBA(Indicator._BAR_WIDTH,
                                        Indicator._BAR_HEIGHT, r, g, b, 0xFF)
            Indicator._barBitmapCache[color] = bitmap
        return Indicator._barBitmapCache[color]
    
    def _updatePositionAndSize():
        if len(Indicator._shownCells) == 0:
            Indicator._frame.Hide()
            return
        # Permit the "suspend" images to show
        if App.isSuspended:
            for cell in Indicator._shownCells:
                if cell[0] == 'suspend': break
            else:
                Indicator._frame.Hide()
                return
        (monitorWidthMult, frameWidthMult, marginX, monitorHeightMult,
         frameHeightMult,
         marginY) = Indicator._POSITIONS[Indicator._currPositionIndex]
        monitor = Indicator._getActiveMonitor()
        frameWidth = Indicator._CELL_WIDTH
        frameHeight = len(Indicator._shownCells) * Indicator._CELL_HEIGHT
        Indicator._frame.SetSize(
            x=int(monitor.x + monitorWidthMult * monitor.width +
                  frameWidthMult * frameWidth + marginX),
            y=int(monitor.y + monitorHeightMult * monitor.height +
                  frameHeightMult * frameHeight + marginY),
            width=frameWidth,
            height=frameHeight)
        Indicator._frame.Show()
    
    def _getActiveMonitor():
        '''That the mouse is on.'''
        mouseX, mouseY = Mouse.getPosition()
        for monitor in screeninfo.get_monitors():
            if (monitor.x <= mouseX < monitor.x + monitor.width and
                    monitor.y <= mouseY < monitor.y + monitor.height):
                return monitor
    
    def _onFrameLeftDown(event):
        # Toggle the indicator's position between primary and secondary.
        Indicator._currPositionIndex = ((Indicator._currPositionIndex + 1) %
                                        len(Indicator._POSITIONS))
        Indicator._updatePositionAndSize()
    
    def _onFrameRightDown(event):
        Icon.showMenu()
    
    def _refresh():
        if not Indicator._isRunning: return # app exited
        # Hide (pop) any cell whose show-time has expired.
        i = 0
        isModified = False
        while i < len(Indicator._shownCells):
            cell = Indicator._shownCells[i]
            cell[1] -= 1 # showTime
            if cell[1] == 0:
                Indicator._shownCells.pop(i)
                isModified = True
                continue
            i += 1
        if isModified:
            Indicator._updateCells()
            Indicator._updatePositionAndSize()
        wx.CallLater(Indicator._REFRESH_INTERVAL, Indicator._refresh)

from pynput import keyboard, mouse

class Keyboard:
    '''Handles the keyboard.'''
    
    # These constant define modifier configurations (e.g. CONTROL | SHIFT).
    NORMAL = 0
    SHIFT = 1 << 0
    CONTROL = 1 << 1
    ALT = 1 << 2
    SUPER = 1 << 3
    FUNCTION = 1 << 4
    GRAPHIC = 1 << 5
    SUSPEND = 1 << 6
    
    _keyboard: keyboard.Controller
    _keyboardListener: keyboard.Listener
    _pressedKey: dict[object, tuple[object, int]] = {}
    '''
    Records the mapped-to key code and modifiers for a pressed key. Useful for
    knowing what key code and modifiers to release when a key is released.
    '''
    _pressedMods = 0
    '''
    The set of modifiers that the user is currently holding down (not virtually
    held down by the software).
    '''
    _numEventsToIgnore = 0
    '''
    The next x events will be ignored (unsuppressed) because they are emitted
    by the software itself. (See `_shouldIgnoreEvent()`.)
    '''
    
    def start():
        '''Starts the keyboard controller and listener in a new thread.'''
        Keyboard._keyboard = keyboard.Controller()
        Keyboard._keyboardListener = keyboard.Listener(
            on_press=Keyboard._onKeyboardPress,
            on_release=Keyboard._onKeyboardRelease,
            suppress=True)
        Keyboard._keyboardListener.start()
    
    def _onKeyboardPress(key):
        key = Keyboard._normalize(key)
        if Keyboard._shouldIgnoreEvent(True, key): return
        if key in Keyboard._SPECIAL_CALLBACK:
            Keyboard._SPECIAL_CALLBACK[key](True)
            return
        keyToPress, mods = Keyboard._NORMAL_LAYOUT.get(key,
                                                       (key, Keyboard.NORMAL))
        Keyboard.pressOrReleaseCombo(True, keyToPress, mods)
        Keyboard._pressedKey[key] = (keyToPress, mods)
    
    def _onKeyboardRelease(key):
        key = Keyboard._normalize(key)
        if Keyboard._shouldIgnoreEvent(False, key): return
        if key in Keyboard._SPECIAL_CALLBACK:
            Keyboard._SPECIAL_CALLBACK[key](False)
            return
        if key not in Keyboard._pressedKey: return
        keyToRelease, mods = Keyboard._pressedKey[key]
        Keyboard.pressOrReleaseCombo(False, keyToRelease, mods)
        Keyboard._pressedKey.pop(key)
    
    def _shouldIgnoreEvent(press, key):
        if Keyboard._numEventsToIgnore > 0:
            # The current keyboard event (press or release) was generated by the
            # software itself and still caught by the listener.
            Keyboard._numEventsToIgnore -= 1
            if Keyboard._numEventsToIgnore == 0:
                Keyboard._keyboardListener._suppress = True
            return True
        if App.isSuspended:
            # TODO: handle suppression-toggle logic here (plus other possible
            # "suspend-permit" keys).
            Keyboard.pressOrRelease(press, key)
            return True
        return False
    
    def _normalize(key):
        if isinstance(key, keyboard.Key):
            # Special keys (such as "shift_r") loses the L/R position info after
            # being normalized.
            return key
        # Normalization (so-called "canonical") turns a KeyCode into its raw
        # form. For instance, when Shift+c is pressed, the KeyCode "C" (capital)
        # gets captured by the listener, and normalizing turns it into "c"
        # (lowercase).
        return Keyboard._keyboardListener.canonical(key)
    
    def pressOrReleaseCombo(press: bool, key: object, mods: int):
        '''
        Sends a press or release event for a `key` with a particular modifier
        configuration defined by `mods` held down.
        
        Args:
            press (bool): Press (`True`) or release (`False`)
            key (str | keyboard.KeyCode | keyboard.Key): The key to press or
                release, e.g., the "t" in Ctrl+Shift+t.
            mods (int): The exact set of modifiers to hold down, e.g.,
                `CONTROL | SHIFT` for the combo Ctrl+Shift+t.
        '''
        if press:
            for mod, modKey in Keyboard._MOD_KEY.items():
                if (bool(Keyboard._pressedMods & mod) != bool(mods & mod)):
                    # The requested modifier is not yet pressed/released
                    Keyboard.pressOrRelease(bool(mods & mod), modKey)
        Keyboard.pressOrRelease(press, key)
        if press:
            for mod, modKey in Keyboard._MOD_KEY.items():
                if (bool(Keyboard._pressedMods & mod) != bool(mods & mod)):
                    # The requested modifier is not yet pressed/released
                    Keyboard.pressOrRelease(not bool(mods & mod), modKey)
    
    def pressOrRelease(press: bool, key: object):
        '''
        Sends a press or release event for a single `key`.
        
        Args:
            press (bool): Press (`True`) or release (`False`)
            key (str | keyboard.KeyCode | keyboard.Key): The key to press or
                release.
        '''
        Keyboard._numEventsToIgnore += 1
        Keyboard._keyboardListener._suppress = False
        if press: Keyboard._keyboard.press(key)
        else: Keyboard._keyboard.release(key)
    
    def pressOrReleaseMod(press: bool, key: object):
        pass
    
    def _pressOrReleaseShift(press):
        pass
    
    def _pressOrReleaseSuspend(press):
        pass
    
    def stop():
        '''
        Stops listening, blocking, and handling any future keyboard events.
        '''
        Keyboard._keyboardListener.stop()
    
    _MOD_KEY = {
        SHIFT: keyboard.Key.shift,
        CONTROL: keyboard.Key.ctrl_l,
        ALT: keyboard.Key.alt_l,
        SUPER: keyboard.Key.cmd_l,
    }
    _SPECIAL_CALLBACK = {
        keyboard.Key.space: _pressOrReleaseShift,
    }
    _PERMITTED_SPECIAL_CALLBACK = {
        keyboard.Key.alt_r: _pressOrReleaseSuspend,
    }
    '''Permitted means allowed to be executed while suspended.'''
    _NORMAL_LAYOUT: dict[object, tuple[object, int]] = {
        keyboard.KeyCode.from_char('`'): (keyboard.Key.tab, NORMAL),
        keyboard.KeyCode.from_char('1'): ('4', SHIFT),
        keyboard.KeyCode.from_char('2'): ('8', SHIFT),
        keyboard.KeyCode.from_char('3'): ('=', SHIFT),
        keyboard.KeyCode.from_char('4'): ('=', NORMAL),
        keyboard.KeyCode.from_char('5'): ('[', SHIFT),
        keyboard.KeyCode.from_char('6'): (']', SHIFT),
        keyboard.KeyCode.from_char('7'): (',', SHIFT),
        keyboard.KeyCode.from_char('8'): ('.', SHIFT),
        keyboard.KeyCode.from_char('9'): ('9', SHIFT),
        keyboard.KeyCode.from_char('0'): ('0', SHIFT),
        keyboard.KeyCode.from_char('-'): ('[', NORMAL),
        keyboard.KeyCode.from_char('='): (']', NORMAL),
        keyboard.Key.tab: ('\\', NORMAL),
        keyboard.KeyCode.from_char('q'): ('\'', NORMAL),
        keyboard.KeyCode.from_char('w'): (',', NORMAL),
        keyboard.KeyCode.from_char('e'): ('.', NORMAL),
        keyboard.KeyCode.from_char('r'): ('p', NORMAL),
        keyboard.KeyCode.from_char('t'): ('y', NORMAL),
        keyboard.KeyCode.from_char('y'): ('f', NORMAL),
        keyboard.KeyCode.from_char('u'): ('g', NORMAL),
        keyboard.KeyCode.from_char('i'): ('c', NORMAL),
        keyboard.KeyCode.from_char('o'): ('r', NORMAL),
        keyboard.KeyCode.from_char('p'): ('l', NORMAL),
        keyboard.KeyCode.from_char('['): ('/', NORMAL),
        keyboard.Key.caps_lock: ('-', NORMAL),
        keyboard.KeyCode.from_char('a'): ('a', NORMAL),
        keyboard.KeyCode.from_char('s'): ('o', NORMAL),
        keyboard.KeyCode.from_char('d'): ('e', NORMAL),
        keyboard.KeyCode.from_char('f'): ('i', NORMAL),
        keyboard.KeyCode.from_char('g'): ('u', NORMAL),
        keyboard.KeyCode.from_char('h'): ('d', NORMAL),
        keyboard.KeyCode.from_char('j'): ('h', NORMAL),
        keyboard.KeyCode.from_char('k'): ('t', NORMAL),
        keyboard.KeyCode.from_char('l'): ('n', NORMAL),
        keyboard.KeyCode.from_char(';'): ('s', NORMAL),
        keyboard.KeyCode.from_char('\''): ('-', SHIFT),
        keyboard.KeyCode.from_char('z'): (';', NORMAL),
        keyboard.KeyCode.from_char('x'): ('q', NORMAL),
        keyboard.KeyCode.from_char('c'): ('j', NORMAL),
        keyboard.KeyCode.from_char('v'): ('k', NORMAL),
        keyboard.KeyCode.from_char('b'): ('x', NORMAL),
        keyboard.KeyCode.from_char('n'): ('b', NORMAL),
        keyboard.KeyCode.from_char('m'): ('m', NORMAL),
        keyboard.KeyCode.from_char(','): ('w', NORMAL),
        keyboard.KeyCode.from_char('.'): ('v', NORMAL),
        keyboard.KeyCode.from_char('/'): ('z', NORMAL),
        keyboard.Key.shift_r: ('3', SHIFT),
    }
    _SHIFT_LAYOUT: dict[object, tuple[object, int]] = {
        keyboard.KeyCode.from_char('`'): (keyboard.Key.tab, SHIFT),
        keyboard.KeyCode.from_char('1'): ('1', NORMAL),
        keyboard.KeyCode.from_char('2'): ('2', NORMAL),
        keyboard.KeyCode.from_char('3'): ('3', NORMAL),
        keyboard.KeyCode.from_char('4'): ('4', NORMAL),
        keyboard.KeyCode.from_char('5'): ('5', NORMAL),
        keyboard.KeyCode.from_char('6'): ('6', NORMAL),
        keyboard.KeyCode.from_char('7'): ('7', NORMAL),
        keyboard.KeyCode.from_char('8'): ('8', NORMAL),
        keyboard.KeyCode.from_char('9'): ('9', NORMAL),
        keyboard.KeyCode.from_char('0'): ('0', NORMAL),
        keyboard.KeyCode.from_char('-'): ('6', SHIFT),
        keyboard.KeyCode.from_char('='): ('`', SHIFT),
        keyboard.Key.tab: ('`', NORMAL),
        keyboard.KeyCode.from_char('q'): ('\'', SHIFT),
        keyboard.KeyCode.from_char('w'): ('1', SHIFT),
        keyboard.KeyCode.from_char('e'): ('/', SHIFT),
        keyboard.KeyCode.from_char('r'): ('p', SHIFT),
        keyboard.KeyCode.from_char('t'): ('y', SHIFT),
        keyboard.KeyCode.from_char('y'): ('f', SHIFT),
        keyboard.KeyCode.from_char('u'): ('g', SHIFT),
        keyboard.KeyCode.from_char('i'): ('c', SHIFT),
        keyboard.KeyCode.from_char('o'): ('r', SHIFT),
        keyboard.KeyCode.from_char('p'): ('l', SHIFT),
        keyboard.KeyCode.from_char('['): ('5', SHIFT),
        keyboard.Key.caps_lock: ('7', SHIFT),
        keyboard.KeyCode.from_char('a'): ('a', SHIFT),
        keyboard.KeyCode.from_char('s'): ('o', SHIFT),
        keyboard.KeyCode.from_char('d'): ('e', SHIFT),
        keyboard.KeyCode.from_char('f'): ('i', SHIFT),
        keyboard.KeyCode.from_char('g'): ('u', SHIFT),
        keyboard.KeyCode.from_char('h'): ('d', SHIFT),
        keyboard.KeyCode.from_char('j'): ('h', SHIFT),
        keyboard.KeyCode.from_char('k'): ('t', SHIFT),
        keyboard.KeyCode.from_char('l'): ('n', SHIFT),
        keyboard.KeyCode.from_char(';'): ('s', SHIFT),
        keyboard.KeyCode.from_char('\''): ('\\', SHIFT),
        keyboard.KeyCode.from_char('z'): (';', SHIFT),
        keyboard.KeyCode.from_char('x'): ('q', SHIFT),
        keyboard.KeyCode.from_char('c'): ('j', SHIFT),
        keyboard.KeyCode.from_char('v'): ('k', SHIFT),
        keyboard.KeyCode.from_char('b'): ('x', SHIFT),
        keyboard.KeyCode.from_char('n'): ('b', SHIFT),
        keyboard.KeyCode.from_char('m'): ('m', SHIFT),
        keyboard.KeyCode.from_char(','): ('w', SHIFT),
        keyboard.KeyCode.from_char('.'): ('v', SHIFT),
        keyboard.KeyCode.from_char('/'): ('z', SHIFT),
        keyboard.Key.shift_r: ('2', SHIFT),
    }
    SHIFT_LOCK_INFLUENCED_KEYS = {
        keyboard.KeyCode.from_char('1'),
        keyboard.KeyCode.from_char('2'),
        keyboard.KeyCode.from_char('3'),
        keyboard.KeyCode.from_char('4'),
        keyboard.KeyCode.from_char('5'),
        keyboard.KeyCode.from_char('6'),
        keyboard.KeyCode.from_char('7'),
        keyboard.KeyCode.from_char('8'),
        keyboard.KeyCode.from_char('9'),
        keyboard.KeyCode.from_char('0'),
        keyboard.KeyCode.from_char('r'),
        keyboard.KeyCode.from_char('t'),
        keyboard.KeyCode.from_char('y'),
        keyboard.KeyCode.from_char('u'),
        keyboard.KeyCode.from_char('i'),
        keyboard.KeyCode.from_char('o'),
        keyboard.KeyCode.from_char('p'),
        keyboard.KeyCode.from_char('a'),
        keyboard.KeyCode.from_char('s'),
        keyboard.KeyCode.from_char('d'),
        keyboard.KeyCode.from_char('f'),
        keyboard.KeyCode.from_char('g'),
        keyboard.KeyCode.from_char('h'),
        keyboard.KeyCode.from_char('j'),
        keyboard.KeyCode.from_char('k'),
        keyboard.KeyCode.from_char('l'),
        keyboard.KeyCode.from_char(';'),
        keyboard.KeyCode.from_char('\''),
        keyboard.KeyCode.from_char('x'),
        keyboard.KeyCode.from_char('c'),
        keyboard.KeyCode.from_char('v'),
        keyboard.KeyCode.from_char('b'),
        keyboard.KeyCode.from_char('n'),
        keyboard.KeyCode.from_char('m'),
        keyboard.KeyCode.from_char(','),
        keyboard.KeyCode.from_char('.'),
        keyboard.KeyCode.from_char('/'),
    }

class Mouse:
    '''Handles the mouse.'''
    
    _mouse: mouse.Controller
    
    def start():
        Mouse._mouse = mouse.Controller()
    
    def getPosition() -> tuple[int, int]:
        '''Returns (x, y); monitor-dependent'''
        return Mouse._mouse.position
    
    def stop():
        pass

if __name__ == '__main__':
    App.start()
