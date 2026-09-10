import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Rectangle {
    id: root
    height: 96
    color: isHovered ? Theme.surfaceHover : Theme.surfaceCard
    radius: Theme.radius
    border.color: isHovered ? Theme.borderHighlight : Theme.border
    border.width: 1

    property var eventData: ({})
    property bool isHovered: false

    signal inspectRequested(string eventId)
    signal askHermesRequested(string eventId)

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 10

        // Snapshot Thumbnail
        Rectangle {
            Layout.preferredWidth: 106
            Layout.preferredHeight: 78
            radius: Theme.radiusSm
            color: Theme.background
            border.color: Theme.border
            clip: true

            Image {
                id: thumb
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                source: {
                    if (root.eventData && root.eventData.snapshot_path) {
                        return "image://trinetra/snapshot/" + root.eventData.snapshot_path;
                    }
                    if (root.eventData && root.eventData.id) {
                        return "image://trinetra/event/" + root.eventData.id;
                    }
                    return "";
                }
            }

            // Severity Strip on Left Edge
            Rectangle {
                width: 3
                height: parent.height
                anchors.left: parent.left
                color: Theme.severityColor(root.eventData ? root.eventData.severity : "")
            }
        }

        // Details Column
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 3

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                // Severity Pill
                Rectangle {
                    height: 18
                    radius: 3
                    width: sevText.implicitWidth + 8
                    color: Theme.severityBg(root.eventData ? root.eventData.severity : "")

                    Text {
                        id: sevText
                        anchors.centerIn: parent
                        text: (root.eventData && root.eventData.severity) ? root.eventData.severity : "INFO"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs - 1
                        font.bold: true
                        color: Theme.severityColor(root.eventData ? root.eventData.severity : "")
                    }
                }

                // Event Type
                Text {
                    text: (root.eventData && root.eventData.type) ? root.eventData.type.replace(/_/g, " ") : "ALERT"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeSm
                    font.bold: true
                    color: Theme.text
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Timestamp
                Text {
                    text: {
                        if (!root.eventData || !root.eventData.ts) return "";
                        var t = root.eventData.ts;
                        return t.length > 19 ? t.substring(11, 19) : t;
                    }
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textMuted
                }
            }

            // Context row: Zone + Source + Tracks
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "Cam: " + ((root.eventData && root.eventData.source_id) ? root.eventData.source_id : "local")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textSecondary
                }

                Text {
                    text: "•"
                    font.pixelSize: 10
                    color: Theme.textDim
                    visible: root.eventData && root.eventData.zone_id
                }

                Text {
                    text: "Zone: " + ((root.eventData && root.eventData.zone_id) ? root.eventData.zone_id : "-")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textSecondary
                    visible: root.eventData && root.eventData.zone_id
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: {
                        var c = (root.eventData && root.eventData.confidence) ? Math.round(root.eventData.confidence * 100) : 100;
                        return "Conf: " + c + "%";
                    }
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs - 1
                    color: Theme.textMuted
                }
            }

            // Action Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                // Investigate Button
                Rectangle {
                    height: 22
                    radius: 3
                    width: auditText.implicitWidth + 12
                    color: auditMa.containsMouse ? Theme.primaryHover : Theme.surfaceElevated
                    border.color: Theme.borderHighlight
                    border.width: 1

                    Text {
                        id: auditText
                        anchors.centerIn: parent
                        text: "🔍 Investigate"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: true
                        color: Theme.text
                    }

                    MouseArea {
                        id: auditMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.eventData && root.eventData.id) {
                                root.inspectRequested(root.eventData.id);
                            }
                        }
                    }
                }

                // Hermes AI Button
                Rectangle {
                    height: 22
                    radius: 3
                    width: hermesBtnText.implicitWidth + 12
                    color: hermesMa.containsMouse ? "#0e7490" : Theme.surfaceElevated
                    border.color: "#155e75"
                    border.width: 1

                    Text {
                        id: hermesBtnText
                        anchors.centerIn: parent
                        text: "⚡ Hermes AI"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: true
                        color: Theme.accent
                    }

                    MouseArea {
                        id: hermesMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.eventData && root.eventData.id) {
                                root.askHermesRequested(root.eventData.id);
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Status Badge / Acknowledge
                Rectangle {
                    height: 20
                    radius: 3
                    width: statusText.implicitWidth + 8
                    color: (root.eventData && root.eventData.status === "reviewed") ? Theme.successBg : Theme.surfaceElevated

                    Text {
                        id: statusText
                        anchors.centerIn: parent
                        text: (root.eventData && root.eventData.status) ? root.eventData.status.toUpperCase() : "NEW"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs - 1
                        color: (root.eventData && root.eventData.status === "reviewed") ? Theme.success : Theme.textMuted
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (bridge && root.eventData && root.eventData.id) {
                                var nextSt = root.eventData.status === "reviewed" ? "new" : "reviewed";
                                bridge.updateEventStatus(root.eventData.id, nextSt);
                                root.eventData.status = nextSt;
                            }
                        }
                    }
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        z: -1
        onEntered: root.isHovered = true
        onExited: root.isHovered = false
        onClicked: {
            if (root.eventData && root.eventData.id) {
                root.inspectRequested(root.eventData.id);
            }
        }
    }
}
