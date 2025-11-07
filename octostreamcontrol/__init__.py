# octostreamcontrol/__init__.py
import os, subprocess
import octoprint.plugin
from datetime import datetime
import shlex
import threading
import json

class OctoStreamControlPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.BlueprintPlugin
):

  ##--- StartupPlugin ---##
  def on_after_startup(self):
    self._logger.info("OctoStreamControl UPDATED VERSION loaded successfully!")
    streams = self._settings.get(["streams"])
    self._logger.info(f"Found {len(streams) if streams else 0} configured streams")

    # Start monitoring thread for recording processes
    import threading
    self._monitoring_thread = threading.Thread(target=self._monitor_recordings, daemon=True, name="RecordingMonitor")
    self._monitoring_thread.start()

  def _monitor_recordings(self):
    """Monitor recording processes and log when they die unexpectedly during prints"""
    import time
    self._logger.info("Recording monitor thread started")

    while True:
      time.sleep(30)  # Check every 30 seconds

      # Only monitor when we have active recordings (i.e., during prints)
      if hasattr(self, "_recordings") and self._recordings:
        for recording in self._recordings[:]:  # Copy list to avoid modification during iteration
          process = recording["process"]
          stream_name = recording["stream_name"]
          start_time = recording.get("start_time", 0)
          elapsed = time.time() - start_time

          if process.poll() is not None:
            # Process has died unexpectedly during the print
            self._logger.error(f"Recording process for '{stream_name}' died after {elapsed:.1f} seconds!")
            self._logger.error(f"Exit code: {process.returncode}")
            self._logger.error(f"Command was: {' '.join(recording['cmd'])}")
            self.send_notification(f"Recording '{stream_name}' stopped unexpectedly!", "error")
            # Don't remove from list here, let stop_recording handle it
          else:
            # Process still alive - log every 2 minutes to confirm it's running
            if int(elapsed) % 120 == 0 or elapsed < 35:  # Log at start and every 2 minutes
              self._logger.info(f"Recording '{stream_name}' alive: {elapsed:.0f}s (PID: {process.pid})")

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
          "enabled": True,
          "upload_to_youtube": False
        }
      ],
      "youtube": {
        "enabled": False,
        "client_secrets_file": "",
        "credentials_file": "",
        "default_title": "3D Print Timelapse - {job_name}",
        "default_description": "3D print recorded on {date}",
        "default_category": "22",  # People & Blogs
        "default_privacy": "unlisted",  # public, unlisted, or private
        "default_tags": "3d printing, timelapse, octoprint"  # Comma-separated string
      }
    }

  def get_settings_version(self):
    return 1

  def on_settings_migrate(self, target, current=None):
    if current is None:
      # First time setup - ensure youtube section exists
      current = 0

    if current < 1:
      # Migrate tags from array to comma-separated string if needed
      tags = self._settings.get(["youtube", "default_tags"])
      if isinstance(tags, list):
        self._settings.set(["youtube", "default_tags"], ", ".join(tags))

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
    #self._logger.info(f"Received event: {event} with payload: {payload}")

    if event == "PrintStarted":
      self._logger.info("Print started - beginning recording")
      self.start_recording()
    elif event in ("PrintDone", "PrintFailed"):
      self._logger.info(f"Print ended ({event}) - stopping recording")
      self.stop_recording()
    else:
      self._logger.debug(f"Ignoring event: {event}")

  ##--- SimpleApiPlugin ---##
  def get_api_commands(self):
    return {
      "start": [],
      "stop": [],
      "status": [],
      "authorize_youtube": [],
      "complete_youtube_auth": ["redirect_url"]
    }

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
    elif command == "authorize_youtube":
      return self.start_youtube_authorization()
    elif command == "complete_youtube_auth":
      redirect_url = data.get("redirect_url")
      return self.complete_youtube_authorization(redirect_url)

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

  ##--- BlueprintPlugin ---##
  # BlueprintPlugin is included but not actively used in the current implementation
  # (kept for potential future enhancements)

  def record_stream(self, url, dir_path, ffmpeg_cmd, filename, stream_name="stream"):
    """
    Record the stream from the given URL to the specified directory using ffmpeg.
    """
    import time

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
      # Use start_new_session=True to detach from parent process lifecycle
      # Redirect output to devnull to prevent buffer issues
      devnull = open(os.devnull, 'w')

      process = subprocess.Popen(
        cmd,
        stdout=devnull,
        stderr=devnull,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent - prevents premature termination
        preexec_fn=lambda: os.nice(10)  # Lower priority (higher nice value)
      )

      # Store devnull file handle so we can close it later
      # (though it doesn't matter much since the process is detached)

      # Track this recording process
      if not hasattr(self, "_recordings"):
        self._recordings = []

      self._recordings.append({
        "process": process,
        "stream_name": stream_name,
        "filename": filename,
        "cmd": cmd,
        "start_time": time.time()
      })

      self._logger.info(f"Started recording stream '{stream_name}' to {filename} (PID: {process.pid})")
      self._logger.info(f"Process is in new session: {os.getsid(process.pid) != os.getsid(os.getpid())}")

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
        self._logger.error(f"FFmpeg process for '{stream_name}' terminated immediately!")
        self._logger.error(f"Exit code: {process.returncode}")
        self._logger.error(f"Check FFmpeg command and stream URL are correct")
        # Remove from recordings list since it failed
        self._recordings = [r for r in self._recordings if r["process"] != process]

    except Exception as e:
      self._logger.error(f"Failed to start ffmpeg process for stream '{stream_name}': {e}")
      raise


  def check_disk_space(self, path, min_free_percent=20):
    """
    Check if there's sufficient disk space available.
    Returns (has_space, free_percent) tuple.
    """
    try:
      import shutil
      stat = shutil.disk_usage(path)
      free_percent = (stat.free / stat.total) * 100
      has_space = free_percent >= min_free_percent
      return has_space, free_percent
    except Exception as e:
      self._logger.error(f"Failed to check disk space for {path}: {e}")
      # Return True to avoid blocking on error, but log the issue
      return True, 0

  def start_youtube_authorization(self):
    """
    Start the YouTube OAuth2 authorization flow - generates auth URL for user.
    Returns Flask response with authorization URL for the user to visit.
    """
    import flask
    try:
      from google_auth_oauthlib.flow import Flow

      youtube_settings = self._settings.get(["youtube"])
      client_secrets = youtube_settings.get("client_secrets_file")
      creds_file = youtube_settings.get("credentials_file")

      if not client_secrets or not os.path.exists(client_secrets):
        error_msg = f"Client secrets file not found: {client_secrets}"
        self._logger.error(error_msg)
        return flask.jsonify(dict(success=False, error=error_msg))

      if not creds_file:
        error_msg = "Credentials file path not configured"
        self._logger.error(error_msg)
        return flask.jsonify(dict(success=False, error=error_msg))

      # Clear any old flow states to avoid issues with multiple authorization attempts
      if hasattr(self, '_youtube_auth_flows'):
        self._youtube_auth_flows.clear()
      else:
        self._youtube_auth_flows = {}

      # Create OAuth flow for web-based authorization
      # Disable HTTPS requirement for localhost development/testing
      import os as os_module
      os_module.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

      # Google doesn't allow custom hostnames like "octopi.local" as redirect URIs
      # Instead, we'll use a localhost redirect with a high port number
      # This creates a URL that the user can copy-paste to complete auth
      redirect_uri = 'http://localhost:8181/'

      self._logger.info(f"Using OAuth redirect URI: {redirect_uri}")

      flow = Flow.from_client_secrets_file(
        client_secrets,
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
        redirect_uri=redirect_uri
      )

      # Generate authorization URL
      auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
      )

      # Store flow state for later use
      self._youtube_auth_flows[state] = {'flow': flow, 'creds_file': creds_file}

      self._logger.info(f"Generated YouTube authorization URL: {auth_url}")

      return flask.jsonify(dict(
        success=True,
        auth_url=auth_url,
        state=state,
        message="Please visit the authorization URL, grant access, and paste the redirect URL back."
      ))

    except ImportError as e:
      error_msg = f"YouTube API libraries not installed: {e}"
      self._logger.error(error_msg)
      return flask.jsonify(dict(success=False, error=error_msg))
    except Exception as e:
      error_msg = f"Failed to start authorization: {e}"
      self._logger.error(error_msg)
      return flask.jsonify(dict(success=False, error=error_msg))

  def complete_youtube_authorization(self, redirect_url):
    """
    Complete YouTube OAuth2 authorization using the redirect URL from the user.
    The user authorizes via Google, which redirects to localhost:8181/?code=...&state=...
    The user copies that full URL and pastes it here.
    """
    import flask
    try:
      import pickle
      from urllib.parse import urlparse, parse_qs

      if not redirect_url:
        return flask.jsonify(dict(success=False, error="No redirect URL provided"))

      self._logger.info(f"Attempting to complete YouTube authorization with redirect URL")

      # Parse the redirect URL to extract code and state
      try:
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        error = params.get('error', [None])[0]

        if error:
          return flask.jsonify(dict(success=False, error=f"Authorization failed: {error}"))

        if not code or not state:
          return flask.jsonify(dict(success=False, error="Invalid redirect URL - missing code or state"))

      except Exception as e:
        return flask.jsonify(dict(success=False, error=f"Failed to parse redirect URL: {e}"))

      # Retrieve the flow we created earlier
      if not hasattr(self, '_youtube_auth_flows') or state not in self._youtube_auth_flows:
        self._logger.error(f"Authorization session not found for state: {state}")
        return flask.jsonify(dict(success=False, error="Authorization session expired. Please start over."))

      flow_data = self._youtube_auth_flows[state]
      flow = flow_data['flow']
      creds_file = flow_data['creds_file']

      self._logger.info("Exchanging authorization code for credentials...")

      # Exchange the authorization code for credentials
      try:
        flow.fetch_token(code=code)
      except Exception as e:
        error_msg = f"Failed to exchange code for token: {e}"
        self._logger.error(error_msg)
        return flask.jsonify(dict(success=False, error=f"Invalid authorization code: {str(e)}"))

      creds = flow.credentials
      self._logger.info(f"Successfully obtained credentials, saving to {creds_file}")

      # Save credentials
      try:
        creds_dir = os.path.dirname(creds_file)
        if creds_dir and not os.path.exists(creds_dir):
          os.makedirs(creds_dir, exist_ok=True)
          self._logger.info(f"Created directory: {creds_dir}")

        with open(creds_file, 'wb') as token:
          pickle.dump(creds, token)

        self._logger.info(f"Successfully saved credentials to {creds_file}")

        # Verify the file was written
        if os.path.exists(creds_file):
          file_size = os.path.getsize(creds_file)
          self._logger.info(f"Credentials file exists, size: {file_size} bytes")
        else:
          self._logger.error(f"Credentials file does not exist after write: {creds_file}")

      except Exception as e:
        error_msg = f"Failed to save credentials file: {e}"
        self._logger.error(error_msg)
        return flask.jsonify(dict(success=False, error=error_msg))

      # Clean up the stored flow
      del self._youtube_auth_flows[state]

      self._logger.info("Successfully authorized and saved credentials")
      self.send_notification("YouTube authorization successful!", "success")

      return flask.jsonify(dict(success=True, message="Authorization complete!"))

    except Exception as e:
      import traceback
      error_msg = f"Failed to complete authorization: {e}"
      self._logger.error(error_msg)
      self._logger.error(traceback.format_exc())
      self.send_notification(f"YouTube authorization failed: {str(e)}", "error")
      return flask.jsonify(dict(success=False, error=str(e)))

  def get_youtube_credentials(self):
    """
    Get YouTube API credentials using OAuth2.
    Returns authenticated credentials object or None if not configured.
    """
    try:
      from google.oauth2.credentials import Credentials
      from google_auth_oauthlib.flow import InstalledAppFlow
      from google.auth.transport.requests import Request
      import pickle

      youtube_settings = self._settings.get(["youtube"])
      creds_file = youtube_settings.get("credentials_file")
      client_secrets = youtube_settings.get("client_secrets_file")

      if not client_secrets or not os.path.exists(client_secrets):
        self._logger.error(f"Client secrets file not found: {client_secrets}")
        return None

      creds = None
      # Load existing credentials if available
      if creds_file and os.path.exists(creds_file):
        try:
          with open(creds_file, 'rb') as token:
            creds = pickle.load(token)

          # Log credential status for debugging
          if creds:
            self._logger.info(f"Loaded YouTube credentials from {creds_file}")
            self._logger.info(f"Credentials valid: {creds.valid}")
            self._logger.info(f"Credentials expired: {creds.expired}")
            self._logger.info(f"Has refresh token: {bool(creds.refresh_token)}")

            # Log expiry information if available
            if hasattr(creds, 'expiry') and creds.expiry:
              from datetime import datetime, timezone
              now = datetime.now(timezone.utc)
              time_until_expiry = creds.expiry - now
              self._logger.info(f"Token expiry: {creds.expiry}")
              self._logger.info(f"Time until expiry: {time_until_expiry}")

        except Exception as e:
          self._logger.warning(f"Failed to load credentials: {e}")

      # If credentials are invalid or don't exist, authenticate
      if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
          try:
            self._logger.info("Attempting to refresh expired YouTube credentials...")
            creds.refresh(Request())
            self._logger.info("Successfully refreshed YouTube credentials")

            # Save refreshed credentials
            if creds_file:
              try:
                os.makedirs(os.path.dirname(creds_file), exist_ok=True)
                with open(creds_file, 'wb') as token:
                  pickle.dump(creds, token)
                self._logger.info(f"Saved refreshed YouTube credentials to {creds_file}")
              except Exception as e:
                self._logger.error(f"Failed to save refreshed credentials: {e}")

          except Exception as e:
            self._logger.error(f"Failed to refresh credentials: {e}")

            # Check if this is the "token expired or revoked" error
            error_str = str(e)
            if "invalid_grant" in error_str or "expired or revoked" in error_str:
              self._logger.error("=" * 80)
              self._logger.error("REFRESH TOKEN EXPIRED OR REVOKED")
              self._logger.error("This typically happens for one of these reasons:")
              self._logger.error("1. Google OAuth consent screen is in 'Testing' mode (tokens expire after 7 days)")
              self._logger.error("2. User revoked access through Google account settings")
              self._logger.error("3. Token hasn't been used for 6+ months")
              self._logger.error("")
              self._logger.error("SOLUTION:")
              self._logger.error("- Go to Google Cloud Console -> OAuth consent screen")
              self._logger.error("- Change status from 'Testing' to 'Production' (or 'In Production')")
              self._logger.error("- Then click 'Authorize YouTube' button in OctoPrint settings to re-authorize")
              self._logger.error("=" * 80)

              # Delete the invalid credentials file so we don't keep trying
              if creds_file and os.path.exists(creds_file):
                try:
                  os.remove(creds_file)
                  self._logger.info(f"Deleted invalid credentials file: {creds_file}")
                except Exception as del_e:
                  self._logger.warning(f"Failed to delete invalid credentials file: {del_e}")

            creds = None

        if not creds:
          # Need to run OAuth flow - this requires user interaction
          self._logger.error("YouTube credentials need to be authorized. Please click 'Authorize YouTube' button in settings.")
          return None

      return creds

    except ImportError as e:
      self._logger.error(f"YouTube API libraries not installed: {e}")
      return None
    except Exception as e:
      self._logger.error(f"Failed to get YouTube credentials: {e}")
      return None

  def upload_to_youtube(self, video_path, stream_name, job_name):
    """
    Upload a video to YouTube using the YouTube Data API.
    Runs in a separate thread to avoid blocking.
    """
    def _upload():
      try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        self._logger.info(f"Starting YouTube upload for {video_path}")

        # Get credentials
        creds = self.get_youtube_credentials()
        if not creds:
          self._logger.error("Failed to get YouTube credentials")
          self.send_notification(f"YouTube upload failed for {stream_name}: No credentials", "error")
          return

        # Build YouTube API client
        youtube = build('youtube', 'v3', credentials=creds)

        # Get settings
        youtube_settings = self._settings.get(["youtube"])
        title_template = youtube_settings.get("default_title", "3D Print Timelapse - {job_name}")
        description_template = youtube_settings.get("default_description", "3D print recorded on {date}")
        category = youtube_settings.get("default_category", "22")
        privacy = youtube_settings.get("default_privacy", "unlisted")
        tags_str = youtube_settings.get("default_tags", "3d printing, timelapse, octoprint")

        # Parse tags from comma-separated string to list
        if isinstance(tags_str, str):
          tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        else:
          # Fallback if somehow it's still a list
          tags = tags_str if isinstance(tags_str, list) else ["3d printing", "timelapse", "octoprint"]

        # Format title and description
        date_str = datetime.now().strftime("%Y-%m-%d")
        title = title_template.format(job_name=job_name, stream_name=stream_name, date=date_str)
        description = description_template.format(job_name=job_name, stream_name=stream_name, date=date_str)

        # Prepare upload metadata
        body = {
          'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': str(category)
          },
          'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
          }
        }

        # Create media upload object
        media = MediaFileUpload(
          video_path,
          mimetype='video/mp4',
          resumable=True,
          chunksize=1024*1024  # 1MB chunks
        )

        # Execute upload
        self._logger.info(f"Uploading video to YouTube: {title}")
        request = youtube.videos().insert(
          part=','.join(body.keys()),
          body=body,
          media_body=media
        )

        response = None
        while response is None:
          status, response = request.next_chunk()
          if status:
            progress = int(status.progress() * 100)
            self._logger.info(f"YouTube upload progress: {progress}%")

        video_id = response.get('id')
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        self._logger.info(f"YouTube upload completed: {video_url}")
        self.send_notification(f"Uploaded {stream_name} to YouTube: {video_url}", "success")

        # Optionally delete local file after successful upload
        # Uncomment if you want to auto-delete:
        # try:
        #   os.remove(video_path)
        #   self._logger.info(f"Deleted local file after upload: {video_path}")
        # except Exception as e:
        #   self._logger.warning(f"Failed to delete local file: {e}")

      except HttpError as e:
        self._logger.error(f"YouTube API error during upload: {e}")
        self.send_notification(f"YouTube upload failed for {stream_name}: {e.error_details}", "error")
      except ImportError as e:
        self._logger.error(f"YouTube API libraries not available: {e}")
        self.send_notification(f"YouTube upload failed: Missing libraries", "error")
      except Exception as e:
        self._logger.error(f"Failed to upload to YouTube: {e}")
        self.send_notification(f"YouTube upload failed for {stream_name}: {str(e)}", "error")

    # Run upload in background thread
    upload_thread = threading.Thread(target=_upload, name=f"YouTubeUpload-{stream_name}")
    upload_thread.daemon = True
    upload_thread.start()

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

    # Check disk space for all enabled streams before starting any recordings
    for i, stream in enumerate(streams):
      if not stream.get("enabled", True):
        continue

      dir_path = stream.get("video_dir")
      stream_name = stream.get("name", f"stream_{i}")

      if not dir_path:
        continue

      has_space, free_percent = self.check_disk_space(dir_path, min_free_percent=20)
      if not has_space:
        error_msg = f"Insufficient disk space for '{stream_name}' ({free_percent:.1f}% free, need at least 20%)"
        self._logger.error(error_msg)
        self.send_notification(error_msg, "error")
        return False
      else:
        self._logger.info(f"Disk space check passed for '{stream_name}': {free_percent:.1f}% free")

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
    youtube_enabled = self._settings.get(["youtube", "enabled"])

    # Get job name for YouTube upload
    job_name = self._printer.get_current_job()['file']['name']
    if not job_name:
      job_name = "manual_recording"

    if hasattr(self, "_recordings"):
      for i, recording in enumerate(self._recordings):
        process = recording["process"]
        stream_name = recording["stream_name"]
        filename = recording["filename"]

        try:
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
            self._logger.error(f"Recording for '{stream_name}' already terminated with exit code {process.returncode}")
            self._logger.error(f"Process may have crashed or been killed externally")

        except Exception as e:
          self._logger.error(f"Error stopping recording for stream '{stream_name}': {e}")

        # Check if we should upload to YouTube - do this regardless of how stopping went
        # As long as the file exists, try to upload it
        try:
          streams = self._settings.get(["streams"])
          stream_config = streams[i] if i < len(streams) else {}
          upload_enabled = stream_config.get("upload_to_youtube", False)

          if youtube_enabled and upload_enabled and os.path.exists(filename):
            self._logger.info(f"Initiating YouTube upload for {filename}")
            self.upload_to_youtube(filename, stream_name, job_name)
          elif youtube_enabled and upload_enabled and not os.path.exists(filename):
            self._logger.warning(f"Cannot upload '{stream_name}' to YouTube: file does not exist at {filename}")
        except Exception as e:
          self._logger.error(f"Error checking YouTube upload for stream '{stream_name}': {e}")

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

