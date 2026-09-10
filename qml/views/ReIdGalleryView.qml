import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: root

    property var identities: bridge ? bridge.getReidIdentities() : []

    signal askHermes(string eventId)

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        // Top Info Bar
        Rectangle {
            Layout.fillWidth: true
            height: 48
            radius: Theme.radius
            color: Theme.surfaceCard
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 12

                Text {
                    text: "CROSS-CAMERA PERSON RE-IDENTIFICATION (RE-ID)"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeSm
                    font.bold: true
                    color: Theme.text
                }

                Rectangle { width: 1; height: 20; color: Theme.border }

                Text {
                    text: "ENGINE: " + (bridge && bridge.reidEnabled ? "FAST-REID ONNX (512-D L2 EMBEDDINGS)" : "DISABLED")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: bridge && bridge.reidEnabled ? Theme.success : Theme.textDim
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: "🔄 Refresh Clusters"
                    font.pixelSize: Theme.fontSizeXs
                    onClicked: {
                        if (bridge) root.identities = bridge.getReidIdentities();
                    }
                }
            }
        }

        // Identities Grid
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            GridView {
                id: reidGrid
                width: parent.width - 16
                cellWidth: 320
                cellHeight: 180
                model: root.identities

                delegate: Rectangle {
                    width: 304
                    height: 168
                    radius: Theme.radius
                    color: Theme.surfaceCard
                    border.color: Theme.border
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            Rectangle {
                                width: 8; height: 8; radius: 4
                                color: Theme.accent
                            }
                            Text {
                                text: modelData.person_id || "GPID_UNKNOWN"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSizeSm
                                font.bold: true
                                color: Theme.accent
                            }
                            Item { Layout.fillWidth: true }
                            Rectangle {
                                height: 18
                                radius: 3
                                width: appText.implicitWidth + 8
                                color: Theme.surfaceElevated
                                Text {
                                    id: appText
                                    anchors.centerIn: parent
                                    text: (modelData.appearances || 1) + " HITS"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSizeXs - 1
                                    color: Theme.textSecondary
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: Theme.border
                        }

                        Text {
                            text: "Cameras: " + (modelData.cameras ? modelData.cameras.join(", ") : "Single Camera")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSizeXs
                            color: Theme.text
                        }

                        Text {
                            text: "First Seen: " + (modelData.first_seen ? modelData.first_seen.substring(11, 19) : "-")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            color: Theme.textSecondary
                        }

                        Text {
                            text: "Last Seen: " + (modelData.last_seen ? modelData.last_seen.substring(11, 19) : "-")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            color: Theme.textSecondary
                        }

                        Item { Layout.fillHeight: true }

                        Button {
                            text: "⚡ Audit with Hermes AI"
                            Layout.fillWidth: true
                            font.pixelSize: Theme.fontSizeXs
                            onClicked: {
                                root.askHermes(modelData.person_id || "");
                            }
                        }
                    }
                }
            }
        }
    }
}
