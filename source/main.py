import gui
import hook
import util

import cmath
import dataclasses
import functools
import math
import time
import typing


@dataclasses.dataclass
class KeyboardState:
    pass


@dataclasses.dataclass
class MouseState:
    pressed_buttons: set[hook.ButtonId]
    is_making_gesture: bool
    recorded_position: hook.CursorPositionPixels
    recorded_time: float


@dataclasses.dataclass
class TrackpadState:
    is_making_gesture: bool
    fingers_making_gesture: set[hook.FingerId]
    prev_recorded_finger_positions: dict[hook.FingerId, hook.FingerPositionInches]
    prev_recorded_time: float
    curr_recorded_finger_positions: dict[hook.FingerId, hook.FingerPositionInches]


GestureMovement = typing.Literal["E", "S", "W", "N"]
Gesture = list[GestureMovement]


@dataclasses.dataclass
class GestureState:
    gesture_source: typing.Literal["mouse", "trackpad"] | None
    gesture_recognized: Gesture
    pending_movement: GestureMovement | None
    pending_movement_distance: float


@dataclasses.dataclass
class AppState:
    is_running: bool
    running_start_time: float


def _handle_hook_key_pressing(
    keyboard_state: KeyboardState,
    hook_state: hook.State,
    key: hook.KeyId,
    is_native_repeat: bool,
) -> hook.ShouldSuppressEventFlag:
    if key == "f4":
        if not is_native_repeat:
            hook.emulate_key_press(hook_state, "shift")
        return True
    elif key == "f5":
        if not is_native_repeat:
            hook.emulate_key_press_with_auto_repeat(hook_state, "volume_down")
        return True
    elif key == "f6":
        if not is_native_repeat:
            hook.emulate_key_press(hook_state, "caps_lock")
        return True
    elif key == "f9":
        if not is_native_repeat:
            hook.emulate_key_press_with_auto_repeat(hook_state, "grave")
        return True
    elif key == "f10":
        hook.emulate_mouse_button_press(hook_state, "left_button")
        hook.emulate_mouse_button_release(hook_state, "left_button")
        hook.emulate_mouse_button_press(hook_state, "left_button")
        hook.emulate_mouse_button_release(hook_state, "left_button")
        return True

    return False


def _handle_hook_key_releasing(
    keyboard_state: KeyboardState, hook_state: hook.State, key: hook.KeyId
) -> hook.ShouldSuppressEventFlag:
    if key == "f4":
        hook.emulate_key_release(hook_state, "shift")
        return True
    elif key == "f5":
        hook.emulate_key_release(hook_state, "volume_down")
        return True
    elif key == "f6":
        hook.emulate_key_release(hook_state, "caps_lock")
        return True
    elif key == "f9":
        hook.emulate_key_release(hook_state, "grave")
        return True

    return False


_MIN_GESTURE_UPDATE_INTERVAL_SECS = 1 / 24
_MIN_SPEED_TO_RECOGNIZE_GESTURE_IN_PER_SEC = 3


def _handle_hook_mouse_button_pressing(
    mouse_state: MouseState,
    hook_state: hook.State,
    gesture_state: GestureState,
    button: hook.ButtonId,
    click_count: int,
) -> hook.ShouldSuppressEventFlag:
    if button == "right_button":
        if gesture_state.gesture_source is None:
            mouse_state.is_making_gesture = True
            mouse_state.recorded_position = hook.get_cursor_position()
            mouse_state.recorded_time = time.time()
            gesture_state.gesture_source = "mouse"
            return True

    return False


def _handle_hook_mouse_button_releasing(
    mouse_state: MouseState,
    hook_state: hook.State,
    gesture_state: GestureState,
    button: hook.ButtonId,
    click_count: int,
) -> hook.ShouldSuppressEventFlag:
    if button == "right_button":
        did_make_gesture = False
        if mouse_state.is_making_gesture:
            if len(gesture_state.gesture_recognized) > 0:
                did_make_gesture = True
                _perform_gestured_action(gesture_state.gesture_recognized)

            mouse_state.is_making_gesture = False
            gesture_state.gesture_source = None
            gesture_state.gesture_recognized.clear()
            gesture_state.pending_movement = None

        if not did_make_gesture:
            hook.emulate_mouse_button_press(hook_state, "right_button")
            hook.emulate_mouse_button_release(hook_state, "right_button")

        return True

    return False


def _update_gesture_from_mouse(
    gesture_state: GestureState,
    mouse_state: MouseState,
    new_cursor_position: hook.CursorPositionPixels,
) -> None:
    curr_time = time.time()
    interval = curr_time - mouse_state.recorded_time
    if interval < _MIN_GESTURE_UPDATE_INTERVAL_SECS:
        return

    prev_pos = mouse_state.recorded_position
    mouse_state.recorded_position = new_cursor_position
    mouse_state.recorded_time = curr_time

    PIXELS_PER_INCH_MOVED = 216

    displacement_pixels = new_cursor_position - prev_pos
    displacement_inches = displacement_pixels / PIXELS_PER_INCH_MOVED
    speed = abs(displacement_inches) / interval
    if speed < _MIN_SPEED_TO_RECOGNIZE_GESTURE_IN_PER_SEC:
        return

    _update_gesture_from_new_displacement(gesture_state, displacement_inches)


def _handle_hook_mouse_cursor_moving(
    mouse_state: MouseState,
    gesture_state: GestureState,
    new_pos: hook.CursorPositionPixels,
) -> None:
    if mouse_state.is_making_gesture:
        _update_gesture_from_mouse(gesture_state, mouse_state, new_pos)


def _handle_hook_mouse_wheel_scrolling(
    scroll_displacement: hook.WheelScrollDisplacementUnits,
    is_continuous: bool,
    is_done_by_momentum: bool,
) -> hook.ShouldSuppressEventFlag:
    return False


def _update_gesture_from_new_displacement(
    gesture_state: GestureState,
    new_displacement_inches: complex,
) -> None:
    direction = (cmath.phase(new_displacement_inches) + math.tau / 8) % math.tau
    movement = ("E", "S", "W", "N")[int(direction / (math.tau / 4))]

    if movement != gesture_state.pending_movement:
        gesture_state.pending_movement = movement
        gesture_state.pending_movement_distance = 0

    gesture_state.pending_movement_distance += abs(new_displacement_inches)

    if (
        len(gesture_state.gesture_recognized)
        and movement == gesture_state.gesture_recognized[-1]
    ):
        return

    MIN_MOVEMENT_DISTANCE_TO_RECOGNIZE_INCHES = 0.25

    if (
        gesture_state.pending_movement_distance
        >= MIN_MOVEMENT_DISTANCE_TO_RECOGNIZE_INCHES
    ):
        gesture_state.gesture_recognized.append(movement)


def _perform_gestured_action(gesture: Gesture) -> None:
    util.log("Gesture made:", "".join(gesture))


_MIN_FINGERS_TO_START_GESTURE_FROM_TRACKPAD = 4


def _update_gesture_from_trackpad(
    gesture_state: GestureState,
    trackpad_state: TrackpadState,
) -> None:
    curr_time = time.time()
    interval = curr_time - trackpad_state.prev_recorded_time
    if interval < _MIN_GESTURE_UPDATE_INTERVAL_SECS:
        return

    prev_pos = trackpad_state.prev_recorded_finger_positions
    curr_pos = trackpad_state.curr_recorded_finger_positions

    trackpad_state.prev_recorded_time = curr_time
    trackpad_state.prev_recorded_finger_positions = curr_pos

    if not trackpad_state.is_making_gesture:
        fingers = set()
        for i in curr_pos:
            if i not in prev_pos:
                continue

            speed = abs(curr_pos[i] - prev_pos[i]) / interval
            if speed >= _MIN_SPEED_TO_RECOGNIZE_GESTURE_IN_PER_SEC:
                fingers.add(i)

        if len(fingers) < _MIN_FINGERS_TO_START_GESTURE_FROM_TRACKPAD:
            return

        trackpad_state.is_making_gesture = True
        trackpad_state.fingers_making_gesture = fingers

    sum_displacement = 0
    fingers_moved = 0

    for i in trackpad_state.fingers_making_gesture:
        if i not in curr_pos or i not in prev_pos:
            continue

        displacement = curr_pos[i] - prev_pos[i]
        speed = abs(displacement) / interval
        if speed < _MIN_SPEED_TO_RECOGNIZE_GESTURE_IN_PER_SEC:
            continue

        sum_displacement += displacement
        fingers_moved += 1

    if fingers_moved == 0:
        return

    mean_displacement = sum_displacement / fingers_moved
    _update_gesture_from_new_displacement(gesture_state, mean_displacement)


def _handle_hook_trackpad_finger_positions_updating(
    trackpad_state: TrackpadState,
    gesture_state: GestureState,
    new_finger_positions: dict[hook.FingerId, hook.FingerPositionInches],
) -> None:
    trackpad_state.curr_recorded_finger_positions = new_finger_positions

    if trackpad_state.is_making_gesture:
        should_end_gesture = True
        for i in trackpad_state.fingers_making_gesture:
            if i in new_finger_positions:
                should_end_gesture = False
                break

        if should_end_gesture:
            if len(gesture_state.gesture_recognized) > 0:
                _perform_gestured_action(gesture_state.gesture_recognized)

            trackpad_state.is_making_gesture = False
            gesture_state.gesture_source = None
            gesture_state.gesture_recognized.clear()
            gesture_state.pending_movement = None

            return

        _update_gesture_from_trackpad(gesture_state, trackpad_state)

    if gesture_state.gesture_source is not None:
        return

    if len(new_finger_positions) >= _MIN_FINGERS_TO_START_GESTURE_FROM_TRACKPAD:
        _update_gesture_from_trackpad(gesture_state, trackpad_state)
        if trackpad_state.is_making_gesture:
            gesture_state.gesture_source = "trackpad"


def stop_running_app(app_state: AppState) -> None:
    app_state.is_running = False


def main() -> None:
    keyboard_state = KeyboardState()
    mouse_state = MouseState(
        pressed_buttons=set(),
        is_making_gesture=False,
        recorded_position=0,
        recorded_time=-math.inf,
    )
    trackpad_state = TrackpadState(
        is_making_gesture=False,
        fingers_making_gesture=set(),
        prev_recorded_finger_positions={},
        prev_recorded_time=-math.inf,
        curr_recorded_finger_positions={},
    )
    gesture_state = GestureState(
        gesture_source=None,
        gesture_recognized=[],
        pending_movement=None,
        pending_movement_distance=0,
    )
    app_state = AppState(
        is_running=True,
        running_start_time=time.time(),
    )

    hook_state = hook.create()
    gui_state = gui.create(
        gui.Handler(
            handle_menu_exit_clicked=functools.partial(stop_running_app, app_state)
        )
    )

    util.ensure_single_instance(
        handle_new_instance_started=functools.partial(stop_running_app, app_state)
    )
    hook.activate(
        hook_state,
        hook.Handler(
            handle_key_pressing=functools.partial(
                _handle_hook_key_pressing, keyboard_state, hook_state
            ),
            handle_key_releasing=functools.partial(
                _handle_hook_key_releasing, keyboard_state, hook_state
            ),
            handle_mouse_button_pressing=functools.partial(
                _handle_hook_mouse_button_pressing,
                mouse_state,
                hook_state,
                gesture_state,
            ),
            handle_mouse_button_releasing=functools.partial(
                _handle_hook_mouse_button_releasing,
                mouse_state,
                hook_state,
                gesture_state,
            ),
            handle_mouse_cursor_moving=functools.partial(
                _handle_hook_mouse_cursor_moving, mouse_state, gesture_state
            ),
            handle_mouse_wheel_scrolling=functools.partial(
                _handle_hook_mouse_wheel_scrolling,
            ),
            handle_trackpad_finger_positions_updating=functools.partial(
                _handle_hook_trackpad_finger_positions_updating,
                trackpad_state,
                gesture_state,
            ),
        ),
    )

    while app_state.is_running:
        hook.process(hook_state)
        gui.process(gui_state)

        MAX_RUN_DURATION_SECS = 30
        if time.time() - app_state.running_start_time >= MAX_RUN_DURATION_SECS:
            stop_running_app(app_state)


if __name__ == "__main__":
    main()
