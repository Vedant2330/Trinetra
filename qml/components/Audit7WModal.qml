import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Dialog {
    id: root
    width: 820
    height: 640
    modal: true
    dim: true
    anchors.centerIn: parent

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLg
        border.color: Theme.borderHighlight
        border.width: 1
    }

    property string eventId: ""
    property var auditData: ({})
    property var eventDetail: ({})

    signal askHermesForEvent(string eventId)

    function loadEvent(evId) {
        root.eventId = evId;
        if (bridge) {
            root.eventDetail = bridge.getEventDetail(evId);
            root.auditData = bridge.generate7WSummary(evId);
        }
        root.open();
    }

    header: Rectangle {
        height: 52
        color: Theme.surfaceCard
        radius: Theme.radiusLg

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 12

            Text {
                text: "🔍 EVENT INVESTIGATION"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSizeMd
                font.bold: true
                color: Theme.text
            }

            Rectangle {
                height: 22
                radius: 3
                width: evIdText.implicitWidth + 12
                color: Theme.surfaceElevated
                border.color: Theme.border

                Text {
                    id: evIdText
                    anchors.centerIn: parent
                    text: root.eventId
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.accent
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "✕"
                flat: true
                onClicked: root.close()
            }
        }
    }

    contentItem: ScrollView {
        clip: true
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        ColumnLayout {
            width: parent.width - 24
            spacing: 14

            // Top Summary Strip
            Rectangle {
                Layout.fillWidth: true
                height: 50
                color: Theme.surfaceCard
                border.color: Theme.border
                radius: Theme.radius

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 16

                    Text {
                        text: (root.eventDetail && root.eventDetail.type) ? root.eventDetail.type.replace(/_/g, " ") : "EVENT"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeMd
                        font.bold: true
                        color: Theme.severityColor(root.eventDetail ? root.eventDetail.severity : "")
                    }

                    Rectangle { width: 1; height: 24; color: Theme.border }

                    Text {
                        text: "Severity: " + ((root.eventDetail && root.eventDetail.severity) ? root.eventDetail.severity : "-")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Rectangle { width: 1; height: 24; color: Theme.border }

                    Text {
                        text: "Status: " + ((root.eventDetail && root.eventDetail.status) ? root.eventDetail.status.toUpperCase() : "NEW")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: (root.eventDetail && root.eventDetail.status === "reviewed") ? Theme.success : Theme.text
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "⚡ Ask Hermes"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: root.askHermesForEvent(root.eventId)
                    }
                }
            }

            // 7-W Grid Cards
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                rowSpacing: 12

                // 1. WHAT
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "1. WHAT (DETECTION & TYPE)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: "Type: " + ((root.auditData && root.auditData.structured) ? root.auditData.structured.what.type : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                        }
                        Text {
                            text: "Severity: " + ((root.auditData && root.auditData.structured) ? root.auditData.structured.what.severity : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                        Text {
                            text: "Confidence: " + ((root.auditData && root.auditData.structured) ? root.auditData.structured.what.confidence : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                    }
                }

                // 2. WHO
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "2. WHO (TRACKS & IDENTITY)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: "Track IDs: " + ((root.auditData && root.auditData.structured) ? JSON.stringify(root.auditData.structured.who.track_ids) : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                        }
                        Text {
                            text: "Global Person ID: " + ((root.auditData && root.auditData.structured && root.auditData.structured.who.global_person_id) ? root.auditData.structured.who.global_person_id : "None (Detection-only)")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                        Text {
                            text: "Cross-Camera Matches: " + ((root.auditData && root.auditData.structured && root.auditData.structured.who.identity_cameras) ? JSON.stringify(root.auditData.structured.who.identity_cameras) : "None")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                    }
                }

                // 3. WHERE
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "3. WHERE (LOCATION & ZONE)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: "Source Camera: " + ((root.auditData && root.auditData.structured) ? root.auditData.structured.where.source_id : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                        }
                        Text {
                            text: "Zone: " + ((root.auditData && root.auditData.structured && root.auditData.structured.where.zone) ? root.auditData.structured.where.zone.name + " (" + root.auditData.structured.where.zone.type + ")" : "Unzoned / Global")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                        Text {
                            text: "Geo Sector: " + ((root.auditData && root.auditData.structured && root.auditData.structured.where.geo_sector) ? root.auditData.structured.where.geo_sector : "Local Facility")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                    }
                }

                // 4. WHEN
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "4. WHEN (TEMPORAL CONTEXT)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: "Timestamp: " + ((root.auditData && root.auditData.structured) ? root.auditData.structured.when.wall_ts : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                        }
                        Text {
                            text: "Video Offset: " + ((root.auditData && root.auditData.structured && root.auditData.structured.when.video_ts !== null) ? root.auditData.structured.when.video_ts + "s" : "Live")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                        Text {
                            text: "Day/Night: " + ((root.auditData && root.auditData.structured) ? (root.auditData.structured.when.is_night ? "NIGHT (Luma < 40)" : "DAY") : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                    }
                }

                // 5. MOVEMENT
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "5. MOVEMENT (KINEMATICS)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: "Direction: " + ((root.auditData && root.auditData.structured && root.auditData.structured.movement.direction) ? root.auditData.structured.movement.direction : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                        }
                        Text {
                            text: "Velocity: " + ((root.auditData && root.auditData.structured && root.auditData.structured.movement.velocity !== null) ? root.auditData.structured.movement.velocity + " px/s" : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                        Text {
                            text: "Trajectory Straightness: " + ((root.auditData && root.auditData.structured && root.auditData.structured.movement.straightness !== null) ? root.auditData.structured.movement.straightness : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.textSecondary
                        }
                    }
                }

                // 6. WHY FLAGGED
                Rectangle {
                    Layout.fillWidth: true
                    height: 120
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "6. WHY FLAGGED (TRIGGER RATIONALE)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }

                        Text {
                            text: (root.auditData && root.auditData.structured && root.auditData.structured.why_flagged) ? root.auditData.structured.why_flagged.reason : "-"
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeSm
                            color: Theme.text
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        Text {
                            text: "Rule: " + ((root.auditData && root.auditData.structured && root.auditData.structured.why_flagged) ? root.auditData.structured.why_flagged.rule : "-")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeXs
                            color: Theme.textSecondary
                        }
                    }
                }
            }

            // 7. EVIDENCE (Snapshot Viewer)
            Rectangle {
                Layout.fillWidth: true
                height: 240
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "7. EVIDENCE (MACHINE-VERIFIED SNAPSHOT)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: true
                            color: Theme.accent
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: (root.eventDetail && root.eventDetail.snapshot_path) ? root.eventDetail.snapshot_path : "No snapshot"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs - 1
                            color: Theme.textMuted
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.background
                        radius: Theme.radiusSm
                        clip: true

                        Image {
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectFit
                            source: {
                                if (root.eventDetail && root.eventDetail.snapshot_path) {
                                    return "image://trinetra/snapshot/" + root.eventDetail.snapshot_path;
                                }
                                if (root.eventId) {
                                    return "image://trinetra/event/" + root.eventId;
                                }
                                return "";
                            }
                        }
                    }
                }
            }
        }
    }
}
