# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OctoStreamControl is an OctoPrint plugin that integrates WebRTC video streaming with automatic recording control. It displays live WebRTC streams in the OctoPrint interface and automatically starts/stops recording when print jobs begin/end.

## Architecture

### Core Plugin Structure
- **Main Plugin Class**: `OctoStreamControlPlugin` in `octostreamcontrol/__init__.py`
- **Plugin Types**: Implements multiple OctoPrint plugin interfaces:
  - `StartupPlugin`, `SettingsPlugin`, `TemplatePlugin`
  - `AssetPlugin`, `EventHandlerPlugin`, `SimpleApiPlugin`

### Key Components
- **Stream Management**: Supports multiple camera streams with individual configurations
- **Recording Logic**: Uses FFmpeg subprocess to record RTSP streams to MP4 files
- **WebRTC Integration**: Embeds WebRTC streams via iframe in OctoPrint tabs
- **Event-Driven Recording**: Automatically starts recording on `PrintStarted` events and stops on print completion/failure events

### Frontend Architecture
- **JavaScript**: Knockout.js view model in `static/js/octostreamcontrol.js`
- **Templates**: Jinja2 templates for settings and tab UI in `templates/`
- **Settings**: Multi-stream configuration with WebRTC/RTSP URLs, FFmpeg commands, and output directories

## Development Commands

### Installation & Development
```bash
# Install for development
task install
# OR
python -m pip install -e .[develop]

# Install/upgrade in OctoPrint environment
source /opt/octopi/oprint/bin/activate
pip install --upgrade .
```

### Build & Distribution
```bash
# Build both sdist and wheel
task build

# Build specific formats
task build-sdist
task build-wheel
```

### Translation Management
```bash
# Extract translatable strings
task babel-extract

# Create new translation
task babel-new -- <locale>

# Update existing translations
task babel-update

# Compile translations
task babel-compile
```

## Stream Configuration

The plugin supports arbitrary numbers of video streams, each with:
- **WebRTC URL**: For live viewing (typically `http://localhost:8889/streamname`)
- **RTSP URL**: For recording (typically `rtsp://localhost:8554/streamname`)
- **FFmpeg Command**: Custom encoding parameters for recordings
- **Output Directory**: Where recorded videos are saved
- **Resolution**: Display dimensions for WebRTC iframe

## External Dependencies

### Required External Tools
- **MediaMTX**: WebRTC streaming server (https://github.com/bluenviron/mediamtx)
- **FFmpeg**: Video encoding for recordings
- **libcamera-utils**: Camera interface (Raspberry Pi specific)

### Typical Streaming Setup
```bash
# Start MediaMTX server
./mediamtx

# Stream from libcamera to RTSP
libcamera-vid -v 0 -t 0 --codec h264 --inline --libav-format h264 -o - | \
ffmpeg -fflags +genpts+igndts -use_wallclock_as_timestamps 1 \
  -f h264 -i - -vf "transpose=2" -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/mystream
```

## File Structure Notes
- Plugin follows standard OctoPrint plugin structure
- Static assets (JS/CSS) in `static/` directory
- Jinja2 templates for UI in `templates/` directory
- Settings configured via multi-stream array structure
- Recording filenames include timestamp and print job name