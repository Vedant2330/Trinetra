import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Rectangle {
    id: root
    height: 48
    color: Theme.surfaceCard
    radius: Theme.radiusLg
    border.color: Theme.border
    border.width: 1

    property var layers: bridge ? bridge.getLayers() : ({})

    Connections {
        target: bridge
        function onLayersUpdated(newLayers) {
            root.layers = newLayers;
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 12

        Text {
            text: "OVERLAYS:"
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontSizeXs
            font.bold: true
            color: Theme.textMuted
            Layout.alignment: Qt.AlignVCenter
        }

        Rectangle {
            width: 1
            height: 24
            color: Theme.border
            Layout.alignment: Qt.AlignVCenter
        }

        Repeater {
            model: [
                { id: "boxes", label: "Boxes", icon: "⬚" },
                { id: "labels", label: "Labels", icon: "🏷" },
                { id: "fps", label: "FPS", icon: "⚡" },
                { id: "trajectories", label: "Trajectories", icon: "〰" },
                { id: "zones", label: "Zones", icon: "⬡" },
                { id: "faces", label: "Faces", icon: "👤" }
            ]

            delegate: Rectangle {
                id: chip
                height: 28
                radius: Theme.radiusSm
                Layout.alignment: Qt.AlignVCenter

                readonly property bool isActive: root.layers && root.layers[modelData.id] === true

                width: chipRow.implicitWidth + 16
                color: isActive ? Theme.primaryMuted : Theme.surfaceHover
                border.color: isActive ? Theme.borderActive : "transparent"
                border.width: 1

                RowLayout {
                    id: chipRow
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                        text: modelData.icon
                        font.pixelSize: 12
                        color: chip.isActive ? Theme.text : Theme.textSecondary
                    }

                    Text {
                        text: modelData.label
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: chip.isActive
                        color: chip.isActive ? Theme.text : Theme.textSecondary
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        if (bridge) {
                            bridge.toggleLayer(modelData.id);
                        }
                    }
                }
            }
        }

        Item { Layout.fillWidth: true }

        // ANPR & Re-ID Capability Indicators
        Rectangle {
            height: 26
            radius: Theme.radiusSm
            width: anprRow.implicitWidth + 16
            color: Theme.surfaceHover
            Layout.alignment: Qt.AlignVCenter

            RowLayout {
                id: anprRow
                anchors.centerIn: parent
                spacing: 6
                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: bridge && bridge.anprMode === "model" ? Theme.success : Theme.warning
                }
                Text {
                    text: "ANPR: " + (bridge ? bridge.anprMode : "off")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textSecondary
                }
            }
        }

        Rectangle {
            height: 26
            radius: Theme.radiusSm
            width: reidRow.implicitWidth + 16
            color: Theme.surfaceHover
            Layout.alignment: Qt.AlignVCenter

            RowLayout {
                id: reidRow
                anchors.centerIn: parent
                spacing: 6
                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: bridge && bridge.reidEnabled ? Theme.accent : Theme.textDim
                }
                Text {
                    text: "Re-ID: " + (bridge && bridge.reidEnabled ? "ONNX" : "DISABLED")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textSecondary
                }
            }
        }
    }
}
