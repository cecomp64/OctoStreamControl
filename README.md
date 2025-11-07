# OctoStreamControl

This plugin displays a WebRTC stream within the OctoPrint GUI, and has provisions to automatically start recording said stream when a print starts,
and stop when the pring stops.  Why?  Well, I happen to be using a rpi5, which does not currently support the `camera-streamer` based 
OctoPi image, which has better support for WebRTC.  I need to use WebRTC because mjpg-streamer produces laggy video, and the timelapse images
are often subject to some sort of auto-exposure artifacts that I can't configure with my camera.  But, video looks great with `libcamera-vid` so
I say, "screw it" and let's just save the damn video.

## Installation

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/cecomp64/OctoStreamControl/archive/master.zip

For development, install with

```
python setup.py install
```

... and update with

```
pip install --upgrade .
```

## Configuration

If you already have a reliable WebRTC stream, just go ahead and enter that stream URL in the corresponding configuration setting.

If you don't already have a WebRTC stream, you can set one up.  See below.

## Set up a WebRTC Stream

### MediaMTX

Download the latest version of `MediaMTX` from GitHub: https://github.com/bluenviron/mediamtx/releases

... and start it up!

```sh
$ ./mediamtx
```

If you want multiple streams (i.e. for multiple cameras) then use a `mediamtx.yml` file, like this:

```yml
paths:
  mystream:
    source: publisher

  usbcam:
    source: publisher
```

### Libcamera and FFMPEG

You may need to install `libcamera-utils` on your pi... ask AI for help if you get any errors.  You should
also already have ffmpeg installed from the OctoPi image.  But... if not... ask AI ;)

Otherwise, start streaming from your camera:

```sh
libcamera-vid -v 0 -t 0 --codec h264 --inline --libav-format h264 -o - | \
ffmpeg -fflags +genpts+igndts -use_wallclock_as_timestamps 1 \
  -f h264 -i - -vf "transpose=2" -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/mystream
```

Now you should have a WebRTC stream available at `localhost:8554/mystream`.  Another camera can also be used, publishing to a different stream.  For my Arducam 5MP USB camera, this is what works for me:

```sh
$ ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -i /dev/video8 \
  -vf "transpose=2,format=yuv420p" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -bsf:v h264_mp4toannexb \
  -pix_fmt yuv420p \
  -f rtsp rtsp://localhost:8554/usbcam  
```

Figure out what video sources are available using this command:

```sh
 v4l2-ctl --list-devices
```

*You may find that USB devices switch their video source across reboots.  If a camera isn't connecting, check the video source in your command*

## YouTube Upload Configuration

OctoStreamControl can automatically upload recorded videos to YouTube after a print completes. To set this up:

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **YouTube Data API v3** for your project

### 2. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Choose application type: **Web application**
4. Under **Authorized redirect URIs**, add: `http://localhost:8181`
   - **Important:** No trailing slash! Must be exactly `http://localhost:8181`
   - Google requires the redirect URI to be `localhost` or a public domain
   - Port `8181` is used to avoid conflicts with common services
5. Click **Create**
6. Download the credentials JSON file
7. Save it somewhere accessible to OctoPrint (e.g., `/home/pi/.config/octoprint/youtube_client_secrets.json`)

**Note:** You'll copy-paste the redirect URL during authorization - no server needs to run on port 8181.

### 3. Set OAuth Consent Screen to Production

**IMPORTANT:** This is the most critical step to avoid token expiration issues!

1. Go to **APIs & Services** → **OAuth consent screen**
2. If your app is in **"Testing"** status:
   - Tokens will **expire after 7 days**
   - You'll see errors like: `invalid_grant: Token has been expired or revoked`
3. Click **"Publish App"** to change status to **"In Production"**
   - For internal use only, you don't need Google's verification
   - Production tokens don't expire (as long as they're used regularly)

### 4. Configure OctoPrint Plugin Settings

1. In OctoPrint, go to **Settings** → **OctoStream Control**
2. Under YouTube settings:
   - Enable YouTube uploads
   - Set **Client Secrets File** path (from step 2)
   - Set **Credentials File** path (where tokens will be stored, e.g., `/home/pi/.config/octoprint/youtube_credentials.pickle`)
   - Configure video title, description, privacy settings, etc.
3. Enable **Upload to YouTube** for each camera stream you want to upload

### 5. Authorize YouTube Access

1. Click the **"Authorize YouTube"** button in settings
2. Copy the authorization URL that appears
3. Open the URL in a browser (can be on any device - phone, laptop, etc.)
4. Sign in to your Google account if prompted
5. Review and grant the requested permissions
6. Google will redirect to `http://localhost:8181?code=...&state=...`
7. **Copy the entire redirect URL** from your browser's address bar
8. Paste the redirect URL into the OctoPrint plugin dialog
9. Click **"Complete Authorization"**

**Important:** When Google redirects to `localhost:8181`, the page won't load (that's normal!). Just copy the full URL from your browser's address bar - it contains the authorization code needed to complete setup.

### Troubleshooting YouTube Uploads

#### "Out-of-Band (OOB) flow has been blocked" Error

Google deprecated the OOB OAuth flow in 2023. If you see this error:

1. Make sure you're using the latest version of OctoStreamControl (which uses localhost redirect flow)
2. In Google Cloud Console, verify your OAuth client is set to **Web application** type
3. Ensure the redirect URI is configured as: `http://localhost:8181` (no trailing slash!)
4. If you previously created a "Desktop app" OAuth client, create a new **Web application** client instead

#### "Invalid redirect URI" or "Redirect URI mismatch" Error

This means the redirect URI in your Google Cloud OAuth client doesn't match what the plugin is using:

1. Go to Google Cloud Console → **APIs & Services** → **Credentials**
2. Edit your OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, ensure you have exactly: `http://localhost:8181`
   - **Must be exact - no trailing slash, no extra characters**
4. Save changes and try authorizing again

#### "Token has been expired or revoked" Error

This means your refresh token is invalid. Common causes:

1. **OAuth consent screen in Testing mode** (7-day expiration) → Change to Production
2. **User revoked access** → Re-authorize through plugin settings
3. **Token unused for 6+ months** → Re-authorize through plugin settings
4. **Password changed** (if Gmail scopes included) → Re-authorize

**Solution:**
- Verify your OAuth consent screen is in "Production" status
- Click "Authorize YouTube" in plugin settings and complete the authorization flow again
- The plugin will automatically delete the invalid token file and prompt for re-authorization

#### Checking Token Status

The plugin logs detailed information about token status:
- Token validity and expiration
- Time until token expiry
- Whether a refresh token is available

Check OctoPrint logs for these details if you encounter issues.

# Development Notes

To push updates once installed:

```sh
source /opt/octopi/oprint/bin/activate
pip install --upgrade .
```

... Then, restart Octoprint.

## Commands

```sh
sudo systemctl stop webcamd
cd mediamtx && ./mediamtx


libcamera-vid -v 0 -t 0 --codec h264 --inline --libav-format h264 --autofocus-mode auto --gain 1.0 -o - | \
ffmpeg -fflags +genpts+igndts -use_wallclock_as_timestamps 1 \
  -f h264 -i - -vf "transpose=2" -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/mystream

ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -i /dev/video8 \
  -vf "transpose=2,format=yuv420p" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -bsf:v h264_mp4toannexb \
  -pix_fmt yuv420p \
  -f rtsp rtsp://localhost:8554/usbcam  

```