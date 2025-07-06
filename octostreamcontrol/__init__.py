# coding=utf-8
from __future__ import absolute_import

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

from octoprint.plugin import (
    StartupPlugin, SettingsPlugin, EventHandlerPlugin, TemplatePlugin
)
import subprocess

class OctoStreamControlPlugin(StartupPlugin, SettingsPlugin, EventHandlerPlugin, TemplatePlugin):

    def on_after_startup(self):
        self._logger.info("OctoStreamControl loaded and ready.")

    def on_event(self, event, payload):
        if event == "PrintStarted":
            self.start_recording()
        elif event in ("PrintCancelled", "PrintFailed", "PrintDone"):
            self.stop_recording()

    def start_recording(self):
        cmd = [
            "/usr/bin/ffmpeg",
            "-y",
            "-i", self._settings.get(["stream_url"]),
            "-c:v", "copy",
            f"/home/pi/videos/print_{self._printer.get_current_job()['file']['name']}.mp4"
        ]
        self._recording_process = subprocess.Popen(cmd)
        self._logger.info("Recording started.")

    def stop_recording(self):
        if hasattr(self, "_recording_process") and self._recording_process.poll() is None:
            self._recording_process.terminate()
            self._logger.info("Recording stopped.")

    def get_settings_defaults(self):
        return {
            "stream_url": "rtsp://localhost:8554/mystream",
            "resolution": "640x360"
        }

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False),
            dict(type="tab", name="Live Stream")
        ]

    def get_api_commands(self):
        return dict(start=[], stop=[])

    def on_api_command(self, command, data):
        if command == "start":
            self.start_recording()
        elif command == "stop":
            self.stop_recording()
