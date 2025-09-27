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
        
        self.startRecording = function() {
            OctoPrint.simpleApiCommand("octostreamcontrol", { action: "start" });
        };
        
        self.stopRecording = function() {
            OctoPrint.simpleApiCommand("octostreamcontrol", { action: "stop" });
        };
        
        self.onBeforeBinding = function() {
            console.log("In onBeforeBinding of OctoStreamControlViewModel");
            self.settings = self.settingsViewModel.settings.plugins.octostreamcontrol;

            // Convert existing streams to observables
            var existingStreams = self.settings.streams() || [];
            var observableStreams = existingStreams.map(function(stream) {
                return {
                    name: ko.observable(stream.name || ""),
                    webrtc_url: ko.observable(stream.webrtc_url || ""),
                    rtsp_url: ko.observable(stream.rtsp_url || ""),
                    ffmpeg_cmd: ko.observable(stream.ffmpeg_cmd || ""),
                    video_dir: ko.observable(stream.video_dir || ""),
                    width: ko.observable(stream.width || "640"),
                    height: ko.observable(stream.height || "480"),
                    enabled: ko.observable(stream.enabled !== false)
                };
            });
            self.streams = ko.observableArray(observableStreams);

            self.addStream = function() {
                console.log("Adding new stream");
                self.streams.push({
                    name: ko.observable(""),
                    webrtc_url: ko.observable(""),
                    rtsp_url: ko.observable(""),
                    ffmpeg_cmd: ko.observable(""),
                    video_dir: ko.observable(""),
                    width: ko.observable("640"),
                    height: ko.observable("480"),
                    enabled: ko.observable(true)
                });
            };

            self.removeStream = function(stream) {
                console.log(`Removing stream ${stream.name()}`);
                self.streams.remove(stream);
            };

            console.log(self);
            console.log(self.settingsViewModel);
        };

        self.onSettingsBeforeSave = function() {
            console.log("Saving settings - syncing streams");
            // Convert observableArray of observables back to plain objects
            var plainStreams = self.streams().map(function(stream) {
                return {
                    name: stream.name(),
                    webrtc_url: stream.webrtc_url(),
                    rtsp_url: stream.rtsp_url(),
                    ffmpeg_cmd: stream.ffmpeg_cmd(),
                    video_dir: stream.video_dir(),
                    width: stream.width(),
                    height: stream.height(),
                    enabled: stream.enabled()
                };
            });
            self.settings.streams(plainStreams);
            console.log("Synced streams:", plainStreams);
        };
    }
    
    OCTOPRINT_VIEWMODELS.push({
        construct: OctoStreamControlViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_octostreamcontrol", "#settings_plugin_octostreamcontrol"]
    });
});
