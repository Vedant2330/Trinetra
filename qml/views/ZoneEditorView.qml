import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: root

    property var zones: bridge ? bridge.getZones("") : []

    Connections {
        target: bridge
        function onZonesUpdated(newZones) {
            root.zones = newZones;
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 12

        // Left Interactive Canvas / Video
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

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
                        text: "ZONE DRAWING TOOLS:"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: true
                        color: Theme.textMuted
                    }

                    Button {
                        text: "➕ Draw Restricted Polygon"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: editorFeed.startDrawing("polygon")
                    }

                    Button {
                        text: "➕ Draw Tripwire Line"
                        font.pixelSize: Theme.fontSizeXs
                        onClicked: editorFeed.startDrawing("line")
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "Click canvas to place points. Double-click or click Done to finish."
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.textSecondary
                    }
                }
            }

            LiveVideoFeed {
                id: editorFeed
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        // Right Zone Management Table
        Rectangle {
            Layout.preferredWidth: 360
            Layout.fillHeight: parent.height
            radius: Theme.radiusLg
            color: Theme.surface
            border.color: Theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "CONFIGURED ZONES (" + (root.zones ? root.zones.length : 0) + ")"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.text
                    }
                }

                ListView {
                    id: zoneList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    model: root.zones

                    delegate: Rectangle {
                        width: zoneList.width
                        height: 72
                        radius: Theme.radius
                        color: Theme.surfaceCard
                        border.color: Theme.border

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            Rectangle {
                                width: 12
                                height: 12
                                radius: 6
                                color: modelData.color || Theme.accent
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                RowLayout {
                                    Text {
                                        text: modelData.name || "Zone"
                                        font.family: Theme.fontSans
                                        font.pixelSize: Theme.fontSizeSm
                                        font.bold: true
                                        color: Theme.text
                                    }
                                    Rectangle {
                                        height: 16
                                        radius: 3
                                        width: kindText.implicitWidth + 6
                                        color: Theme.surfaceElevated
                                        Text {
                                            id: kindText
                                            anchors.centerIn: parent
                                            text: (modelData.kind || "polygon").toUpperCase()
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSizeXs - 2
                                            color: Theme.accent
                                        }
                                    }
                                }

                                Text {
                                    text: "Type: " + (modelData.type || "RESTRICTED") + " • " + (modelData.points ? modelData.points.length : 0) + " vertices"
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontSizeXs
                                    color: Theme.textSecondary
                                }
                            }

                            Button {
                                text: "🗑"
                                flat: true
                                onClicked: {
                                    if (bridge && modelData.id) {
                                        bridge.deleteZone(modelData.id);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
