/*
* View model for OctoStreamControl
*
* Author: Carl Svensson
* License: AGPL-3.0-or-later
*/

$(function() {
    function OctoStreamControlViewModel(parameters) {
        var self = this;
        console.log(parameters);
        self.settingsViewModel = parameters[0];  // Correct naming

        // Recording state observables
        self.isRecording = ko.observable(false);
        self.activeStreams = ko.observable(0);

        self.startRecording = function() {
            console.log("Starting recording...");
            OctoPrint.simpleApiCommand("octostreamcontrol", "start")
                .done(function(response) {
                    console.log("Start recording response:", response);
                    if (response.success) {
                        self.isRecording(response.recording);
                        // Status update will come via plugin message
                    } else {
                        console.error("Failed to start recording");
                    }
                })
                .fail(function() {
                    console.error("Failed to communicate with plugin");
                    new PNotify({
                        title: "Recording Error",
                        text: "Failed to start recording - communication error",
                        type: "error"
                    });
                });
        };

        self.stopRecording = function() {
            console.log("Stopping recording...");
            OctoPrint.simpleApiCommand("octostreamcontrol", "stop")
                .done(function(response) {
                    console.log("Stop recording response:", response);
                    if (response.success) {
                        self.isRecording(response.recording);
                        // Status update will come via plugin message
                    } else {
                        console.error("Failed to stop recording");
                    }
                })
                .fail(function() {
                    console.error("Failed to communicate with plugin");
                    new PNotify({
                        title: "Recording Error",
                        text: "Failed to stop recording - communication error",
                        type: "error"
                    });
                });
        };

        // Check recording status on startup
        self.checkRecordingStatus = function() {
            OctoPrint.simpleApiCommand("octostreamcontrol", "status")
                .done(function(response) {
                    console.log("Recording status:", response);
                    self.isRecording(response.recording);
                    self.activeStreams(response.active_streams);
                });
        };
        
        // Handle plugin messages
        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin !== "octostreamcontrol") return;

            console.log("Received plugin message:", data);

            if (data.type === "notification") {
                // Show notification using PNotify
                new PNotify({
                    title: "OctoStream Control",
                    text: data.message,
                    type: data.notification_type
                });
            } else if (data.type === "recording_state") {
                // Update recording state
                self.isRecording(data.recording);
                self.activeStreams(data.active_streams);
            }
        };

        self.onBeforeBinding = function() {
            console.log("In onBeforeBinding of OctoStreamControlViewModel");
            self.settings = self.settingsViewModel.settings.plugins.octostreamcontrol;

            console.log("Settings object:", self.settings);
            console.log("YouTube settings:", self.settings.youtube);

            // Check initial recording status
            self.checkRecordingStatus();

            // For tab template - keep reference to original settings streams
            self.streams = self.settings.streams;

            // For settings template - use the settings streams directly but make sure they're observable
            // The settings object should already have observables

            self.addStream = function() {
                console.log("Adding new stream");
                var currentStreams = self.settings.streams() || [];
                currentStreams.push({
                    name: "",
                    webrtc_url: "",
                    rtsp_url: "",
                    ffmpeg_cmd: "ffmpeg -i INPUT_URL -c:v libx264 -preset veryfast -crf 25 -g 30 -bf 0 -c:a aac -b:a 128k -movflags +frag_keyframe+empty_moov+faststart",
                    video_dir: "",
                    width: "640",
                    height: "480",
                    enabled: true,
                    upload_to_youtube: false
                });
                self.settings.streams(currentStreams);
            };

            self.removeStream = function(stream) {
                console.log(`Removing stream`);
                var currentStreams = self.settings.streams() || [];
                var index = currentStreams.indexOf(stream);
                if (index > -1) {
                    currentStreams.splice(index, 1);
                    self.settings.streams(currentStreams);
                }
            };

            self.authorizeYouTube = function() {
                console.log("Starting YouTube authorization...");

                new PNotify({
                    title: "YouTube Authorization",
                    text: "Starting authorization flow...",
                    type: "info"
                });

                OctoPrint.simpleApiCommand("octostreamcontrol", "authorize_youtube")
                    .done(function(response) {
                        console.log("YouTube authorization response:", response);
                        if (response.success) {
                            new PNotify({
                                title: "YouTube Authorization",
                                text: response.message || "Please check your browser to complete authorization.",
                                type: "success",
                                hide: false
                            });
                        } else {
                            new PNotify({
                                title: "Authorization Error",
                                text: response.error || "Failed to start authorization",
                                type: "error",
                                hide: false
                            });
                        }
                    })
                    .fail(function() {
                        console.error("Failed to communicate with plugin");
                        new PNotify({
                            title: "Authorization Error",
                            text: "Failed to start authorization - communication error",
                            type: "error"
                        });
                    });
            };

            console.log(self);
            console.log(self.settingsViewModel);
        };

        // Settings will save automatically since we're using the settings object directly
    }
    
    OCTOPRINT_VIEWMODELS.push({
        construct: OctoStreamControlViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_octostreamcontrol", "#settings_plugin_octostreamcontrol"]
    });
});
