from _Framework.DeviceComponent import DeviceComponent
from _Framework.ButtonElement import ButtonElement
from .DeviceControllerStripProxy import DeviceControllerStripProxy
import time
import Live
from .Log import log


class DeviceControllerComponent(DeviceComponent):
    __module__ = __name__
    __doc__ = ''

    def __init__(self, control_surface=None, name="device_component",
        is_enabled=False, matrix=None, side_buttons=None, top_buttons=None):
        self._control_surface = control_surface
        self.name = name
        self._device = None
        self._matrix = matrix
        self._selected_track = None

        # Track navigation buttons
        self._prev_track_button = None
        self._next_track_button = None
        # Track Device navigation buttons
        self._prev_device_button = None
        self._next_device_button = None
        # Device Bank navigation buttons
        self._prev_bank_button = None
        self._next_bank_button = None

        # Precision logic
        self._precision_button = None
        self._precision_mode = False

        # Stepless logic
        self._stepless_button = None
        self._stepless_mode = False

        # Lock logic
        self._lock_button_slots = [None, None, None]
        self._lock_buttons = [None, None, None]
        self._locked_devices = [None, None, None]
        self._locked_device_index = None
        self._lock_buttons = [None, None, None]

        self._locked_device_bank = [0, 0, 0]
        self._lock_button_press = [0, 0, 0]
        self._locked_devices = [None, None, None]

        self._is_active = False
        self._force = True
        self._osd = None

        self._control_surface.application().view.add_is_view_visible_listener(
            'Detail', self._on_detail_view_changed)
        self._control_surface.application().view.add_is_view_visible_listener(
            'Detail/Clip', self._on_views_changed)

        # self._remaining_buttons = None UNUSED
        DeviceComponent.__init__(self)

        # Sliders
        self._sliders = []
        self.set_enabled(is_enabled)

        if top_buttons is not None:
            # device selection buttons
            self.set_prev_device_button(top_buttons[0])
            self.set_next_device_button(top_buttons[1])
            # track selection buttons
            self.set_prev_track_button(top_buttons[2])
            self.set_next_track_button(top_buttons[3])

        if side_buttons is not None:
            # on/off button
            self.set_on_off_button(side_buttons[0])

            # bank nav buttons
            self.set_bank_nav_buttons(side_buttons[1], side_buttons[2])
            self._prev_bank_button = side_buttons[1]
            self._next_bank_button = side_buttons[2]

            # precision
            self.set_precision_button(side_buttons[3])

            # lock buttons
            self.set_lock_button1(side_buttons[4])
            self.set_lock_button2(side_buttons[5])
            self.set_lock_button3(side_buttons[6])
            self.set_stepless_button(side_buttons[7])

        if matrix is not None:
            self.set_matrix(matrix)
        # selected device listener
        self.song().add_appointed_device_listener(self._on_device_changed)
        self._control_surface.set_device_component(self)

    def disconnect(self):
        self._control_surface.application().view.remove_is_view_visible_listener(
            'Detail', self._on_detail_view_changed)
        self._control_surface.application().view.remove_is_view_visible_listener(
            'Detail/Clip', self._on_views_changed)
        self._control_surface.set_device_component(None)
        self.song().remove_appointed_device_listener(self._on_device_changed)
        # LiveDeviceComponent.disconnect(self)
        self._prev_track_button = None
        self._next_track_button = None
        self._prev_device_button = None
        self._next_device_button = None
        self._prev_bank_button = None
        self._next_bank_button = None
        self._precision_button = None
        self._precision_mode = None
        # self._remaining_buttons = None UNUSED
        self._device = None
        for slider in self._sliders:
            slider.shutdown()

    def set_matrix(self, matrix):
        self._matrix = matrix
        if self._matrix:
            self._sliders = []
            for column in range(self._matrix.width()):
                slider = DeviceControllerStripProxy(tuple([
                    self._matrix.get_button(column,
                                            (self._matrix.height() - 1 - row))
                    for row in range(self._matrix.height())]), self, column)
                slider._parent = self
                self._sliders.append(slider)
            self._sliders = tuple(self._sliders)
            self.set_parameter_controls(self._sliders)
        else:
            self._sliders = []

    @property
    def _is_locked_to_device(self):
        return self._locked_device_index is not None

    def set_enabled(self, active):
        if active:
            self._force = True
            self.on_selected_track_changed()
        # disable matrix.
        for slider in self._sliders:
            slider.set_enabled(active)
        # ping parent
        DeviceComponent.set_enabled(self, active)

    def _on_detail_view_changed(self):
        self.update()

    def _on_views_changed(self):
        self.update()

    def set_osd(self, osd):
        self._osd = osd

    def _update_OSD(self):
        if self._osd is not None:
            self._osd.mode = "Device Controller"
            i = 0
            for slider in self._parameter_controls:
                if slider._parameter_to_map_to is not None:
                    self._osd.attribute_names[i] = str(
                        slider._parameter_to_map_to.name)
                    try:
                        self._osd.attributes[i] = str(
                            slider._parameter_to_map_to)
                    except:
                        self._osd.attributes[i] = str(
                            slider._parameter_to_map_to.value)
                else:
                    self._osd.attribute_names[i] = " "
                    self._osd.attributes[i] = " "
                i += 1

            if self._selected_track is not None:
                if self._is_locked_to_device:
                    if self._device is not None:
                        self._osd.info[
                            0] = "track : " + self.get_device_track_name(
                            self._device) + " (locked)"
                    else:
                        self._osd.info[
                            0] = "track : " + self._selected_track.name
                else:
                    self._osd.info[0] = "track : " + self._selected_track.name
            else:
                self._osd.info[0] = " "
            if self._device is not None:
                name = self._device.name
                if name == "":
                    name = "(unamed device)"
                if self._is_locked_to_device:
                    self._osd.info[1] = "device : " + name + " (locked)"
                else:
                    self._osd.info[1] = "device : " + name
            else:
                self._osd.info[1] = "no device selected"
            self._osd.update()

    # DEVICE SELECTION
    def _on_device_changed(self):
        if not self._is_locked_to_device:
            self._selected_track = self.song().view.selected_track
            self.set_device(self.song().appointed_device)
            # self.set_device(self._selected_track.view.selected_device)
            if self.is_enabled():
                self.update()

    def on_selected_track_changed(self):
        if not self._is_locked_to_device:
            self._selected_track = self.song().view.selected_track
            if (self._selected_track.view.selected_device):
                self.set_device(self._selected_track.view.selected_device)
            else:
                self.select_first_device()
            if self.is_enabled():
                self.update()

    def select_first_device(self):
        track = self.song().view.selected_track
        if (track.devices is not None and len(track.devices) > 0):
            device_to_select = track.devices[0]
            self.song().view.select_device(device_to_select)
            self.set_device(device_to_select)

    def set_device(self, device):
        if (device != self._device):
            if self._number_of_parameter_banks() <= self._bank_index:
                self._bank_index = 0
            self._device = device
            self.set_device_view()
            DeviceComponent.set_device(self, device)

    def set_device_view(self):
        view = self.application().view
        if not view.is_view_visible('Detail') or not view.is_view_visible(
            'Detail/DeviceChain'):
            view.show_view('Detail')
            view.show_view('Detail/DeviceChain')

    # UPDATE
    def update(self):

        if self.is_enabled():
            if self._number_of_parameter_banks() <= self._bank_index:
                self._bank_index = 0

            if not self._is_locked_to_device:
                if self._device is not None:
                    if (not self.application().view.is_view_visible(
                        'Detail')) or (
                        not self.application().view.is_view_visible(
                            'Detail/DeviceChain')):
                        self.application().view.show_view('Detail')
                        self.application().view.show_view('Detail/DeviceChain')
            # update bank buttons colors
            if self._device is not None:
                if self._prev_bank_button is not None:
                    self._prev_bank_button.set_on_off_values("Device.Bank.On",
                                                             "Device.Bank.Off")
                if self._next_bank_button is not None:
                    self._next_bank_button.set_on_off_values("Device.Bank.On",
                                                             "Device.Bank.Off")
            else:
                if self._prev_bank_button is not None:
                    self._prev_bank_button.set_on_off_values(
                        "DefaultButton.Disabled", "DefaultButton.Disabled")
                if self._next_bank_button is not None:
                    self._next_bank_button.set_on_off_values(
                        "DefaultButton.Disabled", "DefaultButton.Disabled")
            if self._matrix is not None:
                for x in range(self._matrix.width()):
                    for y in range(self._matrix.height()):
                        self._matrix.get_button(x, y).set_enabled(True)

            if self._device is None and self._matrix is not None:
                for x in range(self._matrix.width()):
                    for y in range(self._matrix.height()):
                        if self._force:
                            self._matrix.get_button(x, y).set_on_off_values(
                                "DefaultButton.Disabled",
                                "DefaultButton.Disabled")
                            self._matrix.get_button(x, y).turn_off()

            # update parent
            DeviceComponent.update(self)
            if self._sliders is not None:
                for slider in self._sliders:
                    slider.reset_if_no_parameter()
            # additional updates :
            self.update_track_buttons()
            self.update_device_buttons()
            self.update_lock_buttons()
            self.update_on_off_button()
            self.update_precision_button()
            self.update_stepless_button()
            self._update_OSD()
            self._force = False

    # LOCK button
    def update_lock_buttons(self):
        # lock button
        if self.is_enabled():
            for index in range(len(self._locked_devices)):
                if self._lock_buttons[index] is not None:
                    if self._locked_devices[index] is not None:
                        self._lock_buttons[index].set_on_off_values(
                            "Device.Lock.Locked", "Device.Lock.Set")
                    else:
                        self._lock_buttons[index].set_on_off_values(
                            "Device.Lock.Empty", "Device.Lock.Empty")  # LED_OFF
                    if self._locked_device_index == index:
                        self._lock_buttons[index].turn_on()
                    else:
                        self._lock_buttons[index].turn_off()

    def set_lock_button1(self, button):
        self.set_lock_button(button, 1)

    def set_lock_button2(self, button):
        self.set_lock_button(button, 2)

    def set_lock_button3(self, button):
        self.set_lock_button(button, 3)

    def set_lock_button4(self, button):
        self.set_lock_button(button, 4)

    def set_lock_button(self, button, index):
        if len(self._lock_buttons) >= index:
            if self._lock_buttons[index - 1] is not None:
                self._lock_buttons[index - 1].remove_value_listener(
                    self._lock_value)
            self._lock_buttons[index - 1] = button
            if self._lock_buttons[index - 1] is not None:
                assert isinstance(self._lock_buttons[index - 1], ButtonElement)
                self._lock_buttons[index - 1].add_value_listener(
                    self._lock_value, identify_sender=True)

    # self.update_lock_buttons()

    def _lock_value(self, value, sender):
        if self.is_enabled():
            index = 0
            for i in range(len(self._lock_buttons)):
                if self._lock_buttons[i] == sender:
                    index = i
            if value != 0:  # Button down
                self._lock_button_press[index] = time.time()
            else:
                now = time.time()
                if now - self._lock_button_press[index] > 0.4:  # long press
                    if self._locked_devices[
                        index] is None:  # If lock is available
                        # save locked device
                        dev = -1
                        for i in range(len(self._locked_devices)):
                            if self._locked_devices[i] == self._device:
                                dev = i
                        if dev >= 0:  # Device already stored
                            if self._device is not None:
                                self._control_surface.show_message(
                                    "*** WARNING *** '" + self.get_device_track_name(
                                        self._device) + " - " + str(
                                        self._device.name) + "' IS ALREADY IN LOCK: " + str(
                                        dev + 1))
                        else:  # New device is added
                            if self._device is not None:
                                self._locked_devices[index] = self._device
                                if self._device is not None:
                                    self._control_surface.show_message(
                                        " '" + self.get_device_track_name(
                                            self._device) + " - " + str(
                                            self._device.name) + "' STORED IN LOCK: " + str(
                                            index + 1))
                                    self._locked_device_index = index
                                    self.update()

                    else:  # Lock was used
                        # remove saved device
                        if self._locked_devices[index] is not None:
                            self._control_surface.show_message(
                                "REMOVING '" + self.get_device_track_name(
                                    self._locked_devices[index]) + " - " + str(
                                    self._locked_devices[
                                        index].name) + "' FROM LOCK: " + str(
                                    index + 1))
                            self._locked_devices[index] = None
                            self._locked_device_index = None
                else:  # Short press
                    # use selected device
                    if self._locked_device_index == index:
                        if self._locked_devices[index] is not None:
                            if self._locked_devices[index] is not None:
                                self._control_surface.show_message(
                                    "UNLOCKED FROM '" + self.get_device_track_name(
                                        self._locked_devices[
                                            index]) + " - " + str(
                                        self._locked_devices[
                                            index].name) + "' (" + str(
                                        index + 1) + ")")
                        self._locked_device_index = None
                    elif self._locked_devices[index] is not None:
                        self._locked_device_index = index
                        self.set_device(self._locked_devices[index])
                        if self._locked_devices[index] is not None:
                            self._control_surface.show_message(
                                "LOCKED TO '" + self.get_device_track_name(
                                    self._locked_devices[index]) + " - " + str(
                                    self._locked_devices[
                                        index].name) + " (" + str(
                                    index + 1) + ")")
                        self.update()
            self.update_track_buttons()
            self.update_device_buttons()
            self._update_OSD()
            if self._is_locked_to_device:
                self.on_selected_track_changed()
            self.update_lock_buttons()

    def get_device_track_name(self, device):
        if str(type(device)) == "<class 'Track.Track'>":
            return str(device.name)
        else:
            return self.get_device_track_name(device.canonical_parent)

    # Precision button
    def update_precision_button(self):
        if self._precision_button is not None and self.is_enabled():
            if self._precision_button is not None:
                if self._device is not None:
                    self._precision_button.set_on_off_values(
                        "Device.PrecisionSlider.On",
                        "Device.PrecisionSlider.Off")
                    if self._precision_mode:
                        self._precision_button.turn_on()
                    else:
                        self._precision_button.turn_off()
                else:
                    self._precision_button.set_on_off_values(
                        "DefaultButton.Disabled", "DefaultButton.Disabled")
                    self._precision_button.turn_off()

    def _precision_value(self, value, sender):
        if ((not sender.is_momentary()) or (value is not 0)):
            if (self._precision_button is not None and self.is_enabled()):
                self._precision_mode = not self._precision_mode
                self.update_precision_button()
                for slider in self._sliders:
                    slider.set_precision_mode(self._precision_mode)

    def set_precision_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if self._precision_button != button:
            if self._precision_button is not None:
                self._precision_button.remove_value_listener(
                    self._precision_value)
            self._precision_button = button
            if self._precision_button is not None:
                assert isinstance(button, ButtonElement)
                self._precision_button.add_value_listener(self._precision_value,
                                                          identify_sender=True)
                self.update()

    # Stepless Button
    def update_stepless_button(self):
        if self._stepless_button is not None and self.is_enabled():
            if self._stepless_button is not None:
                if self._device is not None:
                    self._stepless_button.set_on_off_values(
                        "Device.SteplessSlider.On", "Device.SteplessSlider.Off")
                    if self._stepless_mode:
                        self._stepless_button.turn_on()

                    else:
                        self._stepless_button.turn_off()
                else:
                    self._stepless_button.set_on_off_values(
                        "DefaultButton.Disabled", "DefaultButton.Disabled")
                    self._stepless_button.turn_off()

    def _stepless_value(self, value, sender):
        if ((not sender.is_momentary()) or (value is not 0)):
            if (self._stepless_button is not None and self.is_enabled()):
                self._stepless_mode = not self._stepless_mode
                self.update_stepless_button()
                if self._stepless_mode:
                    self._control_surface.show_message("Stepless Mode On")
                else:
                    self._control_surface.show_message("Stepless Mode Off")
                for slider in self._sliders:
                    slider.set_stepless_mode(self._stepless_mode)

    def set_stepless_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if self._stepless_button != button:
            if self._stepless_button is not None:
                self._stepless_button.remove_value_listener(
                    self._stepless_value)
            self._stepless_button = button
            if self._stepless_button is not None:
                assert isinstance(button, ButtonElement)
                self._stepless_button.add_value_listener(self._stepless_value,
                                                         identify_sender=True)
                self.update()

    # ON OFF button
    def update_on_off_button(self):
        # on/off button
        if self._on_off_button is not None and self.is_enabled():
            if self._on_off_button is not None:
                parameter = self._on_off_parameter()
                if parameter is not None:
                    self._on_off_button.set_on_off_values("Mode.Device.On",
                                                          "Mode.Device.Off")
                    if parameter.is_enabled and parameter.value > 0:
                        self._on_off_button.turn_on()
                    else:
                        self._on_off_button.turn_off()
                else:
                    self._on_off_button.set_on_off_values(
                        "DefaultButton.Disabled", "DefaultButton.Disabled")
                    self._on_off_button.turn_off()

    def _on_off_value(self, value):
        if self._on_off_button is not None and self.is_enabled():
            DeviceComponent._on_off_value(self, value)
            self.update_on_off_button()

    def set_on_off_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if self._on_off_button != button:
            if self._on_off_button is not None:
                self._on_off_button.remove_value_listener(self._on_off_value)
            self._on_off_button = button
            if self._on_off_button is not None:
                assert isinstance(button, ButtonElement)
                self._on_off_button.add_value_listener(self._on_off_value)

    # TRACKS Buttons
    def update_track_buttons(self):
        # tracks
        if self.is_enabled():
            if (self._prev_track_button is not None):
                self._prev_track_button.set_on_off_values("Mode.Track.On",
                                                          "Mode.Track.Off")

                if self.selected_track_idx is not None and self.selected_track_idx > 0 and not self._is_locked_to_device:
                    self._prev_track_button.turn_on()
                else:
                    self._prev_track_button.turn_off()

            if (self._next_track_button is not None):
                self._next_track_button.set_on_off_values("Mode.Track.On",
                                                          "Mode.Track.Off")

                if self.selected_track_idx is not None and self.selected_track_idx < len(
                    self.song().tracks) - 1 and not self._is_locked_to_device:
                    self._next_track_button.turn_on()
                else:
                    self._next_track_button.turn_off()

    def set_next_track_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._next_track_button != button):
            if (self._next_track_button is not None):
                self._next_track_button.remove_value_listener(
                    self._next_track_value)
            self._next_track_button = button
            if (self._next_track_button is not None):
                assert isinstance(button, ButtonElement)
                self._next_track_button.add_value_listener(
                    self._next_track_value, identify_sender=True)

    def _next_track_value(self, value, sender):
        assert (self._next_track_button is not None)
        assert (value in range(128))
        if self.is_enabled():
            if ((not sender.is_momentary()) or (value is not 0)):
                if self.selected_track_idx is not None and self.selected_track_idx < len(
                    self.song().tracks) - 1 and not self._is_locked_to_device:
                    self.song().view.selected_track = self.song().tracks[
                        self.selected_track_idx + 1]
                    self.update()

    def set_prev_track_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._prev_track_button != button):
            if (self._prev_track_button is not None):
                self._prev_track_button.remove_value_listener(
                    self._prev_track_value)
            self._prev_track_button = button
            if (self._prev_track_button is not None):
                assert isinstance(button, ButtonElement)
                self._prev_track_button.set_on_off_values("Mode.Device.On",
                                                          "Mode.Device.Off")
                self._prev_track_button.add_value_listener(
                    self._prev_track_value, identify_sender=True)

    def _prev_track_value(self, value, sender):
        assert (self._prev_track_button is not None)
        assert (value in range(128))
        if ((not sender.is_momentary()) or (value is not 0)):
            if self.is_enabled():
                if self.selected_track_idx is not None and self.selected_track_idx > 0 and not self._is_locked_to_device:
                    self.song().view.selected_track = self.song().tracks[
                        self.selected_track_idx - 1]
                    self.update()

    @property
    def selected_track_idx(self):
        tracks = list(self.song().tracks)
        result = tracks.index(
            self.song().view.selected_track) if self.song().view.selected_track in tracks else None
        return result

    # return self.tuple_idx(self.song().tracks, self.song().view.selected_track)

    def selected_track(self):
        return self.song().view.selected_track

    # DEVICES

    def update_device_buttons(self):

        if self.is_enabled():
            if (self._prev_device_button is not None):
                self._prev_device_button.set_on_off_values("Mode.Device.On",
                                                           "Mode.Device.Off")

                if self.selected_track().devices is not None and (
                    len(self.selected_track().devices) > 0 and self.selected_device_idx > 0 and not self._is_locked_to_device):
                    self._prev_device_button.turn_on()
                else:
                    self._prev_device_button.turn_off()

            if (self._next_device_button is not None):
                self._next_device_button.set_on_off_values("Mode.Device.On",
                                                           "Mode.Device.Off")

                if (
                    len(self.selected_track().devices) > 0 and self.selected_device_idx < len(
                    self.selected_track().devices) - 1 and not self._is_locked_to_device):
                    self._next_device_button.turn_on()
                else:
                    self._next_device_button.turn_off()

    # DEVICE NAVIGATION LISTENERES
    def set_next_device_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._next_device_button != button):
            if (self._next_device_button is not None):
                self._next_device_button.remove_value_listener(
                    self._next_device_value)
            self._next_device_button = button
            if (self._next_device_button is not None):
                assert isinstance(button, ButtonElement)
                self._next_device_button.add_value_listener(
                    self._next_device_value, identify_sender=True)

    def _next_device_value(self, value, sender):
        assert (self._next_device_button is not None)
        assert (value in range(128))
        if self.is_enabled():
            if ((not sender.is_momentary()) or (value is not 0)):
                if self.selected_track() is not None and len(
                    self.selected_track().devices) > 0:
                    if (self.selected_device_idx < len(
                        self.selected_track().devices) - 1 and not self._is_locked_to_device):
                        direction = Live.Application.Application.View.NavDirection.right
                        self._control_surface.application().view.scroll_view(
                            direction, 'Detail/DeviceChain', True)
                        # self.song().view.select_device(self.selected_track().devices[self.selected_device_idx + 1])
                        self.update()

    def set_prev_device_button(self, button):
        assert (isinstance(button, (ButtonElement, type(None))))
        if (self._prev_device_button != button):
            if (self._prev_device_button is not None):
                self._prev_device_button.remove_value_listener(
                    self._prev_device_value)
            self._prev_device_button = button
            if (self._prev_device_button is not None):
                assert isinstance(button, ButtonElement)
                self._prev_device_button.add_value_listener(
                    self._prev_device_value, identify_sender=True)

    def _prev_device_value(self, value, sender):
        assert (self._prev_device_button is not None)
        assert (value in range(128))
        if self.is_enabled():
            if ((not sender.is_momentary()) or (value is not 0)):
                if self.selected_track() is not None and len(
                    self.selected_track().devices) > 0:
                    if (
                        self.selected_device_idx > 0 and not self._is_locked_to_device):
                        direction = Live.Application.Application.View.NavDirection.left
                        self._control_surface.application().view.scroll_view(
                            direction, 'Detail/DeviceChain', True)
                        # self.song().view.select_device(self.selected_track().devices[self.selected_device_idx - 1])
                        self.update()

    @property
    def selected_device_idx(self):
        devices = list(self.song().view.selected_track.devices)
        result = devices.index(
            self._device) if self._device in devices else None
        # return self.tuple_idx(self.song().view.selected_track.devices, self._device)
        return result

    # DEVICE BANK BUTTONS
    def set_prev_bank_button(self, button):
        self._prev_bank_button = button
        if self._prev_bank_button is not None and self._next_bank_button is not None or self._prev_bank_button is None and self._next_bank_button is None:
            self.set_bank_nav_buttons(self._prev_bank_button,
                                      self._next_bank_button)

    def set_next_bank_button(self, button):
        self._next_bank_button = button
        if self._prev_bank_button is not None and self._next_bank_button is not None or self._prev_bank_button is None and self._next_bank_button is None:
            self.set_bank_nav_buttons(self._prev_bank_button,
                                      self._next_bank_button)

# utils

# def tuple_idx(self, tuple, obj):
#	for i in xrange(0, len(tuple)):
#		if (tuple[i] == obj):
#			return i
#	return(False)
