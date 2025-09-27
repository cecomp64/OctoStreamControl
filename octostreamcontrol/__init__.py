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

  ##--- StartupPlugin ---##
  def on_after_startup(self):
    self._logger.info("OctoStreamControl UPDATED VERSION loaded successfully!")
    streams = self._settings.get(["streams"])
    self._logger.info(f"Found {len(streams) if streams else 0} configured streams")

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
          "ffmpeg_cmd": "ffmpeg -i INPUT_URL -c:v libx264 -preset slow -crf 23 -c:a aac -b:a 128k -movflags +faststart",
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

    # Replace INPUT_URL placeholder with actual URL, or use old format if no placeholder
    if "INPUT_URL" in ffmpeg_cmd:
      cmd_with_url = ffmpeg_cmd.replace("INPUT_URL", url)
      cmd = shlex.split(cmd_with_url) + [filename]
    else:
      # Legacy format: ffmpeg options without -i
      cmd = shlex.split(ffmpeg_cmd) + ["-i", url, filename]
    self._logger.info(f"Executing FFmpeg command for '{stream_name}': {' '.join(cmd)}")

    try:
      process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
      )

      # Track this recording process
      if not hasattr(self, "_recordings"):
        self._recordings = []

      self._recordings.append({
        "process": process,
        "stream_name": stream_name,
        "filename": filename,
        "cmd": cmd
      })

      self._logger.info(f"Started recording stream '{stream_name}' to {filename} (PID: {process.pid})")

      # Check if process started successfully (give it a moment)
      import time
      time.sleep(0.5)
      if process.poll() is not None:
        # Process already terminated
        stdout, stderr = process.communicate()
        self._logger.error(f"FFmpeg process for '{stream_name}' terminated immediately!")
        self._logger.error(f"Exit code: {process.returncode}")
        self._logger.error(f"STDOUT: {stdout}")
        self._logger.error(f"STDERR: {stderr}")
        # Remove from recordings list since it failed
        self._recordings = [r for r in self._recordings if r["process"] != process]

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
          process = recording["process"]
          stream_name = recording["stream_name"]

          if process.poll() is None:
            # Process is still running, terminate it
            process.terminate()
            # Wait a bit for graceful termination
            try:
              process.wait(timeout=5)
              self._logger.info(f"Stopped recording for stream '{stream_name}'")
            except subprocess.TimeoutExpired:
              # Force kill if it doesn't terminate gracefully
              process.kill()
              self._logger.warning(f"Force killed recording process for stream '{stream_name}'")
          else:
            # Process already terminated, check why
            stdout, stderr = process.communicate()
            self._logger.error(f"Recording for '{stream_name}' already terminated with exit code {process.returncode}")
            if stderr:
              self._logger.error(f"FFmpeg stderr for '{stream_name}': {stderr}")

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

