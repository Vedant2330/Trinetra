import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: root

    signal inspectEvent(string eventId)
    signal askHermes(string eventId)

    RowLayout {
        anchors.fill: parent
        spacing: 12

        // Main Video Area
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            // Top Source Control Bar
            Rectangle {
                Layout.fillWidth: true
                height: 48
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    Text {
                        text: "SOURCE FEED:"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: true
                        color: Theme.textMuted
                    }

                    Button {
                        text: "📹 Webcam (Cam 0)"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: {
                            if (bridge) bridge.startWebcam(0);
                        }
                    }

                    Button {
                        text: "📁 Add Video"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: {
                            if (bridge) {
                                var file = bridge.selectVideoFile();
                                if (file && file !== "") {
                                    bridge.startFile(file);
                                }
                            }
                        }
                    }

                    Button {
                        text: "⏹ Stop Stream"
                        font.pixelSize: Theme.fontSizeXs
                        enabled: bridge && bridge.sessionStatus === "running"
                        onClicked: {
                            if (bridge) bridge.stopSession();
                        }
                    }

                    Rectangle { width: 1; height: 20; color: Theme.border }

                    Button {
                        text: "➕ Add Polygon Zone"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: videoFeed.startDrawing("polygon")
                    }

                    Button {
                        text: "➕ Add Tripwire Line"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: videoFeed.startDrawing("line")
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: hermesDrawer.visible ? "⚡ Hide Hermes AI" : "⚡ Open Hermes AI"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: hermesDrawer.visible = !hermesDrawer.visible
                    }
                }
            }

            // Live Feed Display
            LiveVideoFeed {
                id: videoFeed
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        // Right Live Event Stream
        Rectangle {
            Layout.preferredWidth: 380
            Layout.fillHeight: parent.height
            radius: Theme.radiusLg
            color: Theme.surface
            border.color: Theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                // Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "LIVE EVENTS"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.text
                    }

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        height: 20
                        radius: 3
                        width: countTxt.implicitWidth + 8
                        color: Theme.surfaceElevated

                        Text {
                            id: countTxt
                            anchors.centerIn: parent
                            text: (bridge ? bridge.eventsList.length : 0) + " EVENTS"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs - 1
                            color: Theme.textSecondary
                        }
                    }
                }

                // Events List View
                ListView {
                    id: eventsList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    model: bridge ? bridge.eventsList : []

                    delegate: EventCard {
                        width: eventsList.width
                        eventData: modelData
                        onInspectRequested: function(evId) {
                            root.inspectEvent(evId);
                        }
                        onAskHermesRequested: function(evId) {
                            hermesDrawer.visible = true;
                            hermesPanel.setScopedEvent(evId);
                            hermesPanel.sendPrompt("Perform a full forensic breakdown for event " + evId);
                        }
                    }
                }
            }
        }

        // Hermes AI Side Panel (Dockable / Toggleable)
        Rectangle {
            id: hermesDrawer
            visible: false
            Layout.preferredWidth: 420
            Layout.fillHeight: parent.height
            radius: Theme.radiusLg
            color: Theme.surface
            border.color: Theme.borderHighlight
            border.width: 1

            HermesPanel {
                id: hermesPanel
                anchors.fill: parent
            }
        }
    }
}
