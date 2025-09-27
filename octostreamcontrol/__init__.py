# octostreamcontrol/__init__.py
import os, subprocess
from octoprint.plugin import (
  StartupPlugin, SettingsPlugin, TemplatePlugin,
  AssetPlugin, EventHandlerPlugin, SimpleApiPlugin
)
from datetime import datetime
import shlex

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
        "user": "cecomp64",
        "repo": "octostreamcontrol",
        "current": self._plugin_version,

        "pip": "https://github.com/cecomp64/octostreamcontrol/archive/{target_version}.zip"
      }
    }

  ##--- SettingsPlugin ---##
  def get_settings_defaults(self):
    return {
      "streams": [
        {
          "name": "Camera 1",
          "webrtc_url": "http://localhost:8889/mystream",
          "rtsp_url": "rtsp://localhost:8554/mystream",
          "video_dir": "/home/pi/videos",
          "ffmpeg_cmd": "ffmpeg -c:v libx264 -preset slow -crf 23 -c:a aac -b:a 128k -movflags +faststart",
          "width": "640",
          "height": "360",
          "enabled": True
        }
      ]
    }

    ## this injects these vars into your tab template
  def get_template_vars(self):
    self._logger.info("Injecting template vars into tab")
    return {
       "streams": self._settings.get(["streams"])
    }

  ##--- TemplatePlugin ---##
  def get_template_configs(self):
    return [
      {
        "type": "settings",
        "custom_bindings": True
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
    self._logger.info(f"Received event: {event} with payload: {payload}")

    if event == "PrintStarted":
      self._logger.info("Print started - beginning recording")
      self.start_recording()
    elif event in ("PrintDone", "PrintFailed", "PrintCancelled"):
      self._logger.info(f"Print ended ({event}) - stopping recording")
      self.stop_recording()
    else:
      self._logger.debug(f"Ignoring event: {event}")

  ##--- SimpleApiPlugin ---##
  def get_api_commands(self):
    return {"start": [], "stop": []}

  def on_api_command(self, command, data):
    if command == "start":
      self.start_recording()
    elif command == "stop":
      self.stop_recording()

  def record_stream(self, url, dir_path, ffmpeg_cmd, filename, stream_name="stream"):
    """
    Record the stream from the given URL to the specified directory using ffmpeg.
    """
    # Make the directory if it doesn't exist
    if not os.path.exists(dir_path):
      os.makedirs(dir_path)

    cmd = shlex.split(ffmpeg_cmd) + ["-i", url, filename]

    try:
      process = subprocess.Popen(cmd)

      # Track this recording process
      if not hasattr(self, "_recordings"):
        self._recordings = []

      self._recordings.append({
        "process": process,
        "stream_name": stream_name,
        "filename": filename
      })

      self._logger.info(f"Started recording stream '{stream_name}' to {filename}")

    except Exception as e:
      self._logger.error(f"Failed to start ffmpeg process for stream '{stream_name}': {e}")
      raise


  ##--- Recording logic ---##
  def start_recording(self):
    streams = self._settings.get(["streams"])
    if not streams:
      self._logger.error("No streams configured")
      return

    job_name = self._printer.get_current_job()['file']['name']
    if not job_name:
      job_name = "default_job"

    # Create base filename with timestamp
    job_name = job_name.replace(" ", "_").replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{timestamp}_{job_name}"
    base_filename = base_filename[:50]  # Limit length to avoid filename issues
    base_filename = base_filename.replace(":", "-").replace(".", "-")

    # Initialize list to track recording processes
    if not hasattr(self, "_recordings"):
      self._recordings = []

    # Start recording for each enabled stream
    for i, stream in enumerate(streams):
      if not stream.get("enabled", True):
        continue

      url = stream.get("rtsp_url")
      dir_path = stream.get("video_dir")
      ffmpeg_cmd = stream.get("ffmpeg_cmd")
      stream_name = stream.get("name", f"stream_{i}")

      if not all([url, dir_path, ffmpeg_cmd]):
        self._logger.error(f"Missing configuration for stream '{stream_name}': url={url}, dir_path={dir_path}, ffmpeg_cmd={ffmpeg_cmd}")
        continue

      # Create unique filename for this stream
      safe_stream_name = stream_name.replace(" ", "_").replace("/", "_")
      filename = f"{base_filename}_{safe_stream_name}.mp4"
      filepath = os.path.join(dir_path, filename)

      try:
        self.record_stream(url, dir_path, ffmpeg_cmd, filepath, stream_name)
      except Exception as e:
        self._logger.error(f"Failed to start recording for stream '{stream_name}': {e}")

  def stop_recording(self):
    if hasattr(self, "_recordings"):
      for recording in self._recordings:
        try:
          if recording["process"].poll() is None:
            recording["process"].terminate()
            self._logger.info(f"Stopped recording for stream '{recording['stream_name']}'")
        except Exception as e:
          self._logger.error(f"Error stopping recording for stream '{recording['stream_name']}': {e}")

      self._recordings = []

    # Legacy support for single recording
    if hasattr(self, "_rec") and self._rec.poll() is None:
      self._rec.terminate()
      self._logger.info("Stopped legacy recording")

__plugin_name__ = "OctoStream Control"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctoStreamControlPlugin()

