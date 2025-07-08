# octostreamcontrol/__init__.py
import os, subprocess
from octoprint.plugin import (
  StartupPlugin, SettingsPlugin, TemplatePlugin,
  AssetPlugin, EventHandlerPlugin, SimpleApiPlugin
)
from datetime import datetime

class OctoStreamControlPlugin(
    StartupPlugin,
    SettingsPlugin,
    TemplatePlugin,
    AssetPlugin,
    EventHandlerPlugin,
    SimpleApiPlugin
):

  ##--- Plugin metadata (optional, but helps) ---##
  def get_update_information(self):
    return {
      "octostreamcontrol": {
        "displayName": "OctoStream Control",
        "displayVersion": self._plugin_version,

        # version check URL etc...
        "type": "github_release",
        "user": "you",
        "repo": "octostreamcontrol",
        "current": self._plugin_version,

        "pip": "https://github.com/you/octostreamcontrol/archive/{target_version}.zip"
      }
    }

  ##--- SettingsPlugin ---##
  def get_settings_defaults(self):
    return {
      "stream_url": "http://localhost:8889/mystream",
      "rstp_url": "rtsp://localhost:8554/mystream",
      "video_dir": "/home/pi/videos",
      "ffmpeg_cmd": "ffmpeg -c:v libx264 -preset slow -crf 23 -c:a aac -b:a 128k -movflags +faststart",
      "resolution": "640x360"
    }

    ## this injects these vars into your tab template
  def get_template_vars(self):
    self._logger.info("Injecting template vars into tab")
    stream = self._settings.get(["stream_url"])
    self._logger.info(f"Injecting stream_url into template: {stream}")
    return {
       "stream_url": stream,
       "rstp_url": self._settings.get(["rstp_url"]),
       "ffmpeg_cmd": self._settings.get(["ffmpeg_cmd"]),
       "resolution": self._settings.get(["resolution"]),
       "video_dir": self._settings.get(["video_dir"])
    }

  ##--- TemplatePlugin ---##
  def get_template_configs(self):
    return [
      {
        "type": "settings",
        "custom_bindings": False
      },
      {
        "type": "tab",
        "template": "octostreamcontrol_tab.jinja2",
        "custom_bindings": True
      }
    ]

  ##--- AssetPlugin ---##
  def get_assets(self):
    return {
      "js": ["js/octostreamcontrol.js"],
      "css": ["css/octostreamcontrol.css"]
    }

  ##--- EventHandlerPlugin ---##
  def on_event(self, event, payload):
    if event == "PrintStarted":
      self.start_recording()
    elif event in ("PrintDone", "PrintFailed", "PrintCancelled"):
      self.stop_recording()

  ##--- SimpleApiPlugin ---##
  def get_api_commands(self):
    return {"start": [], "stop": []}

  def on_api_command(self, command, data):
    if command == "start":
      self.start_recording()
    elif command == "stop":
      self.stop_recording()

  ##--- Recording logic ---##
  def start_recording(self):
    url   = self._settings.get(["rstp_url"])
    dir_path = self._settings.get(['video_dir'])
    ffmpeg_cmd = self._settings.get(['ffmpeg_cmd'])
    job_name = self._printer.get_current_job()['file']['name']

    # Create a timestamped filename
    if not job_name:
      job_name = "default_job"
    job_name = job_name.replace(" ", "_").replace("/", "_")

    # Compute a timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_name = f"{timestamp}_{job_name}"
    job_name = job_name[:50]  # Limit length to avoid filename issues
    job_name = job_name.replace(":", "-")  # Replace colons to avoid issues
    job_name = job_name.replace(".", "-")  # Replace dots to avoid issues
    fname = os.path.join(dir_path, f"{job_name}.mp4")

    # Make the directory if it doesn't exist
    if not os.path.exists(dir_path):
      os.makedirs(dir_path)

    # rtsp://localhost:8554/mystream
    cmd   = [ffmpeg_cmd, "-i", url, fname]
    self._rec = subprocess.Popen(cmd)
    self._logger.info(f"Started recording to {fname}")

  def stop_recording(self):
    if hasattr(self, "_rec") and self._rec.poll() is None:
      # Log the contents of stderr and stdout if needed
      stdout, stderr = self._rec.communicate()
      if stdout:
        self._logger.info(f"FFmpeg stdout: {stdout.decode('utf-8')}")
      if stderr:
        self._logger.error(f"FFmpeg stderr: {stderr.decode('utf-8')}")

      # Terminate the ffmpeg process
      self._rec.terminate()
      self._logger.info("Stopped recording")

__plugin_name__ = "OctoStream Control"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctoStreamControlPlugin()
