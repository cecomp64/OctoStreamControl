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

            // Ensure all existing streams have the upload_to_youtube property
            if (self.settings.streams) {
                var streams = self.settings.streams();
                if (streams && Array.isArray(streams)) {
                    streams.forEach(function(stream) {
                        if (stream.upload_to_youtube === undefined) {
                            stream.upload_to_youtube = false;
                        }
                    });
                    // Trigger update to ensure observables are created
                    self.settings.streams(streams);
                }
            }

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
                        if (response.success && response.auth_url) {
                            // Open the authorization URL in a new tab FIRST
                            window.open(response.auth_url, '_blank');

                            // Show a non-blocking custom confirmation dialog using PNotify
                            new PNotify({
                                title: "YouTube Authorization",
                                text: "A new tab has been opened for Google authorization.\n\n" +
                                      "After you authorize:\n" +
                                      "1. Google will redirect to localhost:8181\n" +
                                      "2. Copy the FULL URL from your browser's address bar\n" +
                                      "3. Click the button below to paste it",
                                type: "info",
                                hide: false,
                                confirm: {
                                    confirm: true,
                                    buttons: [{
                                        text: 'Complete Authorization',
                                        addClass: 'btn-primary',
                                        click: function(notice) {
                                            notice.remove();
                                            self.showAuthUrlModal();
                                        }
                                    }, {
                                        text: 'Cancel',
                                        click: function(notice) {
                                            notice.remove();
                                            new PNotify({
                                                title: "Authorization Cancelled",
                                                text: "Click 'Authorize YouTube' again when ready.",
                                                type: "info"
                                            });
                                        }
                                    }]
                                },
                                buttons: {
                                    closer: false,
                                    sticker: false
                                }
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

            self.showAuthUrlModal = function() {
                // Create a modal dialog for non-blocking URL input
                var modalHtml =
                    '<div class="modal fade" id="youtube-auth-modal" tabindex="-1">' +
                    '  <div class="modal-dialog">' +
                    '    <div class="modal-content">' +
                    '      <div class="modal-header">' +
                    '        <button type="button" class="close" data-dismiss="modal">&times;</button>' +
                    '        <h4 class="modal-title">Complete YouTube Authorization</h4>' +
                    '      </div>' +
                    '      <div class="modal-body">' +
                    '        <p>After authorizing with Google, paste the <strong>full redirect URL</strong> below:</p>' +
                    '        <p><small>Example: <code>http://localhost:8181?state=...&code=...</code></small></p>' +
                    '        <input type="text" class="form-control" id="youtube-redirect-url" placeholder="http://localhost:8181?state=...&code=..." style="width: 100%;">' +
                    '      </div>' +
                    '      <div class="modal-footer">' +
                    '        <button type="button" class="btn btn-default" data-dismiss="modal">Cancel</button>' +
                    '        <button type="button" class="btn btn-primary" id="youtube-auth-submit">Submit</button>' +
                    '      </div>' +
                    '    </div>' +
                    '  </div>' +
                    '</div>';

                // Remove any existing modal
                $('#youtube-auth-modal').remove();

                // Add modal to page
                $('body').append(modalHtml);

                // Show modal
                $('#youtube-auth-modal').modal('show');

                // Focus on input when modal is shown
                $('#youtube-auth-modal').on('shown.bs.modal', function() {
                    $('#youtube-redirect-url').focus();
                });

                // Handle submit button
                $('#youtube-auth-submit').click(function() {
                    var redirectUrl = $('#youtube-redirect-url').val().trim();

                    if (redirectUrl) {
                        // Close modal
                        $('#youtube-auth-modal').modal('hide');

                        // Send the redirect URL back to complete authorization
                        new PNotify({
                            title: "YouTube Authorization",
                            text: "Processing authorization...",
                            type: "info"
                        });

                        OctoPrint.simpleApiCommand("octostreamcontrol", "complete_youtube_auth", {
                            redirect_url: redirectUrl
                        }).done(function(completeResponse) {
                            if (completeResponse.success) {
                                new PNotify({
                                    title: "YouTube Authorization",
                                    text: "Authorization successful! You can now upload videos to YouTube.",
                                    type: "success",
                                    hide: false
                                });
                            } else {
                                new PNotify({
                                    title: "Authorization Error",
                                    text: completeResponse.error || "Failed to complete authorization",
                                    type: "error",
                                    hide: false
                                });
                            }
                        }).fail(function() {
                            new PNotify({
                                title: "Authorization Error",
                                text: "Failed to complete authorization - communication error",
                                type: "error"
                            });
                        });
                    } else {
                        new PNotify({
                            title: "Invalid Input",
                            text: "Please paste the redirect URL",
                            type: "warning"
                        });
                    }
                });

                // Also allow Enter key to submit
                $('#youtube-redirect-url').keypress(function(e) {
                    if (e.which === 13) {
                        $('#youtube-auth-submit').click();
                    }
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
