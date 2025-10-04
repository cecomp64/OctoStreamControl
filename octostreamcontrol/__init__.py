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
          "ffmpeg_cmd": "ffmpeg -i INPUT_URL -t 0 -c:v libx264 -preset veryfast -crf 25 -g 30 -bf 0 -c:a aac -b:a 128k -movflags +frag_keyframe+empty_moov+faststart",
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
    return {"start": [], "stop": [], "status": []}

  def on_api_command(self, command, data):
    import flask
    if command == "start":
      success = self.start_recording()
      return flask.jsonify(dict(success=success, recording=self.is_recording()))
    elif command == "stop":
      success = self.stop_recording()
      return flask.jsonify(dict(success=success, recording=self.is_recording()))
    elif command == "status":
      return flask.jsonify(dict(recording=self.is_recording(), active_streams=self.get_active_stream_count()))

  def is_recording(self):
    """Check if any streams are currently recording"""
    if not hasattr(self, "_recordings"):
      return False
    # Check if any recording processes are still alive
    active_recordings = [r for r in self._recordings if r["process"].poll() is None]
    return len(active_recordings) > 0

  def get_active_stream_count(self):
    """Get count of active recording streams"""
    if not hasattr(self, "_recordings"):
      return 0
    return len([r for r in self._recordings if r["process"].poll() is None])

  def send_notification(self, message, type="info"):
    """Send notification to frontend"""
    self._plugin_manager.send_plugin_message(self._identifier, dict(
      type="notification",
      message=message,
      notification_type=type
    ))

  def record_stream(self, url, dir_path, ffmpeg_cmd, filename, stream_name="stream"):
    """
    Record the stream from the given URL to the specified directory using ffmpeg.
    """
    # Make the directory if it doesn't exist
    if not os.path.exists(dir_path):
      os.makedirs(dir_path)

    # Replace INPUT_URL placeholder with actual URL, or use old format if no placeholder
    self._logger.info(f"Configured FFmpeg command for '{stream_name}': {' '.join(ffmpeg_cmd)}")
    if "INPUT_URL" in ffmpeg_cmd:
      cmd_with_url = ffmpeg_cmd.replace("INPUT_URL", url)
      cmd = shlex.split(cmd_with_url) + [filename]
    else:
      # Legacy format: ffmpeg options without -i
      cmd = shlex.split(ffmpeg_cmd) + ["-i", url, filename]
    self._logger.info(f"Executing FFmpeg command for '{stream_name}': {' '.join(cmd)}")

    try:
      # Start FFmpeg with lower priority to avoid interfering with OctoPrint
      process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        preexec_fn=lambda: os.nice(10)  # Lower priority (higher nice value)
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

      # Log system resources for diagnostics
      try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        self._logger.info(f"System resources at recording start - CPU: {cpu_percent}%, Memory: {memory.percent}%")
      except ImportError:
        self._logger.info("psutil not available for resource monitoring")

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
      self.send_notification("No streams configured", "error")
      return False

    # Check if already recording
    if self.is_recording():
      self._logger.warning("Recording already in progress")
      self.send_notification("Recording already in progress", "warning")
      return False

    job_name = self._printer.get_current_job()['file']['name']
    if not job_name:
      job_name = "manual_recording"

    # Create base filename with timestamp
    job_name = job_name.replace(" ", "_").replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{timestamp}_{job_name}"
    base_filename = base_filename[:50]  # Limit length to avoid filename issues
    base_filename = base_filename.replace(":", "-").replace(".", "-")

    # Initialize list to track recording processes
    if not hasattr(self, "_recordings"):
      self._recordings = []

    successful_starts = 0
    enabled_streams = 0

    # Start recording for each enabled stream
    for i, stream in enumerate(streams):
      if not stream.get("enabled", True):
        continue

      enabled_streams += 1
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
        successful_starts += 1
      except Exception as e:
        self._logger.error(f"Failed to start recording for stream '{stream_name}': {e}")

    # Send notification about recording status
    if successful_starts > 0:
      if successful_starts == enabled_streams:
        self.send_notification(f"Started recording {successful_starts} stream(s)", "success")
      else:
        self.send_notification(f"Started recording {successful_starts} of {enabled_streams} streams", "warning")

      # Broadcast state change
      self._plugin_manager.send_plugin_message(self._identifier, dict(
        type="recording_state",
        recording=True,
        active_streams=successful_starts
      ))
      return True
    else:
      self.send_notification("Failed to start recording any streams", "error")
      return False

  def stop_recording(self):
    if not self.is_recording():
      self._logger.warning("No recording in progress")
      self.send_notification("No recording in progress", "warning")
      return False

    stopped_count = 0
    total_active = self.get_active_stream_count()

    if hasattr(self, "_recordings"):
      for recording in self._recordings:
        try:
          process = recording["process"]
          stream_name = recording["stream_name"]

          if process.poll() is None:
            # Process is still running, send SIGTERM for graceful shutdown
            import signal
            import os
            try:
              # Send SIGTERM first (allows FFmpeg to finalize the file)
              process.terminate()
              self._logger.info(f"Sent termination signal to recording process for stream '{stream_name}'")

              # Wait longer for FFmpeg to finalize the video file properly
              process.wait(timeout=30)
              self._logger.info(f"Stopped recording for stream '{stream_name}' gracefully")
              stopped_count += 1

            except subprocess.TimeoutExpired:
              # If still running after 30 seconds, send SIGINT (Ctrl+C equivalent)
              try:
                if hasattr(signal, 'SIGINT'):
                  os.kill(process.pid, signal.SIGINT)
                  self._logger.info(f"Sent SIGINT to recording process for stream '{stream_name}'")
                  process.wait(timeout=10)
                  self._logger.info(f"Stopped recording for stream '{stream_name}' with SIGINT")
                  stopped_count += 1
              except (subprocess.TimeoutExpired, ProcessLookupError):
                # Last resort - force kill
                try:
                  process.kill()
                  self._logger.warning(f"Force killed recording process for stream '{stream_name}' as last resort")
                  stopped_count += 1
                except ProcessLookupError:
                  # Process already dead
                  pass
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
      stopped_count += 1

    # Send notification about stop status
    if stopped_count > 0:
      if stopped_count == total_active:
        self.send_notification(f"Stopped recording {stopped_count} stream(s)", "success")
      else:
        self.send_notification(f"Stopped {stopped_count} of {total_active} streams", "warning")
    else:
      self.send_notification("No active recordings to stop", "info")

    # Broadcast state change
    self._plugin_manager.send_plugin_message(self._identifier, dict(
      type="recording_state",
      recording=False,
      active_streams=0
    ))

    return stopped_count > 0

__plugin_name__ = "OctoStream Control"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctoStreamControlPlugin()

