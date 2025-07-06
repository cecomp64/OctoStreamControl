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

Now you should have a WebRTC stream available at `localhost:8554/mystream`.