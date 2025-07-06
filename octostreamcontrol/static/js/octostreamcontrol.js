/*
 * View model for OctoStreamControl
 *
 * Author: Carl Svensson
 * License: AGPL-3.0-or-later
 */

$(function() {
    function OctoStreamControlViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.streamSrc = ko.computed(() => self.settings.settings.stream_url());

        self.startRecording = function() {
            OctoPrint.simpleApiCommand("octostreamcontrol", { action: "start" });
        };

        self.stopRecording = function() {
            OctoPrint.simpleApiCommand("octostreamcontrol", { action: "stop" });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: OctoStreamControlViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_octostreamcontrol"]
    });
});
