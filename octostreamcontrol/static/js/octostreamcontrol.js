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
            self.streams = ko.observableArray(self.settings.streams());
            
            self.addStream = function() {
                console.log("Adding new stream");
                self.streams.push({ name: "", webrtc_url: "", rtsp_url: "", ffmpeg_cmd: "", video_dir: "", width: "640", height: "480", enabled: true });
            };
            
            self.removeStream = function(stream) {
                console.log(`Removing stream ${stream.name}`);
                self.streams.remove(stream);
            };
            
            self.onBeforeSave = function() {
                self.settings.streams(self.streams());
            };

            console.log(self);
            console.log(self.settingsViewModel);
        };
    }
    
    OCTOPRINT_VIEWMODELS.push({
        construct: OctoStreamControlViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_octostreamcontrol", "#settings_plugin_octostreamcontrol"]
    });
});
