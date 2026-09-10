import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components"
import "views"
import "."

ApplicationWindow {
    id: window
    width: 1440
    height: 900
    minimumWidth: 1024
    minimumHeight: 700
    visible: true
    title: "TRINETRA // DEFENSE TACTICAL COMMAND CENTER"
    color: Theme.background

    property int activeNavIndex: 0

    Connections {
        target: bridge
        function onStatusMessage(msg, level) {
            toast.show(msg, level);
        }
    }

    // Main Layout: Sidebar Navigation + Content Area
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Left Navigation Rail
        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: Theme.navBackground
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                // Brand Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 54
                    color: "transparent"

                    RowLayout {
                        anchors.fill: parent
                        spacing: 12

                        Rectangle {
                            width: 36
                            height: 36
                            color: Theme.accent
                            radius: 4
                        }

                        ColumnLayout {
                            spacing: 2
                            Text {
                                text: "TRINETRA"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSizeLg
                                font.bold: true
                                color: Theme.navText
                            }
                            Text {
                                text: "COMMAND CENTER"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSizeXs
                                color: Theme.navTextMuted
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#334155" // Muted border for nav
                }

                Item { height: 8 }

                // Nav Items
                Repeater {
                    model: [
                        { label: "Live Operations", icon: "🔴", index: 0 },
                        { label: "Events", icon: "🔔", index: 1 },
                        { label: "Geography", icon: "🗺️", index: 2 },
                        { label: "Re-ID", icon: "👤", index: 3 },
                        { label: "System", icon: "⚙️", index: 4 }
                    ]

                    delegate: Rectangle {
                        id: navBtn
                        Layout.fillWidth: true
                        height: 42
                        radius: Theme.radius
                        color: window.activeNavIndex === modelData.index ? "#334155" : (navMa.containsMouse ? "#1E293B" : "transparent")
                        border.color: "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 10

                            Text {
                                text: modelData.icon
                                font.pixelSize: 14
                                color: window.activeNavIndex === modelData.index ? Theme.navText : Theme.navTextMuted
                            }

                            Text {
                                text: modelData.label
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSizeSm
                                font.bold: window.activeNavIndex === modelData.index
                                color: window.activeNavIndex === modelData.index ? Theme.navText : Theme.navTextMuted
                            }
                        }

                        MouseArea {
                            id: navMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: window.activeNavIndex = modelData.index
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                // Footer System Status
                Rectangle {
                    Layout.fillWidth: true
                    height: 52
                    radius: Theme.radius
                    color: "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: bridge && bridge.sessionStatus === "running" ? Theme.success : Theme.warning
                        }

                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: "CORE RUNTIME"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSizeXs - 1
                                font.bold: true
                                color: Theme.navTextMuted
                            }
                            Text {
                                text: bridge ? bridge.sessionStatus.toUpperCase() : "OFFLINE"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSizeXs
                                color: Theme.navText
                            }
                        }
                    }
                }
            }
        }

        // View Stack Area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.background
            anchors.margins: 14

            StackLayout {
                anchors.fill: parent
                currentIndex: window.activeNavIndex

                DashboardView {
                    onInspectEvent: function(evId) {
                        auditModal.loadEvent(evId);
                    }
                }

                EventsForensicView {
                    onInspectEvent: function(evId) {
                        auditModal.loadEvent(evId);
                    }
                    onAskHermes: function(evId) {
                        auditModal.loadEvent(evId);
                    }
                }

                ZoneEditorView {}

                ReIdGalleryView {
                    onAskHermes: function(personId) {
                        toast.show("Querying Hermes for Re-ID person: " + personId, "info");
                    }
                }

                DiagnosticsView {}
            }
        }
    }

    // Investigation Modal Dialog
    Audit7WModal {
        id: auditModal
        onAskHermesForEvent: function(evId) {
            window.activeNavIndex = 0; // jump to dashboard
            toast.show("Scoped Hermes AI to event: " + evId, "info");
        }
    }

    // Toast Notification Banner
    Rectangle {
        id: toast
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        height: 40
        radius: Theme.radius
        color: Theme.surfaceElevated
        border.color: Theme.primary
        border.width: 1
        visible: false
        opacity: 0

        property string message: ""
        property string level: "info"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 8

            Text {
                text: toast.level === "success" ? "✓" : (toast.level === "error" ? "⚠" : "ℹ")
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSizeSm
                font.bold: true
                color: toast.level === "success" ? Theme.success : (toast.level === "error" ? Theme.danger : Theme.accent)
            }

            Text {
                text: toast.message
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSizeSm
                color: Theme.text
            }
        }

        NumberAnimation on opacity {
            id: toastAnim
            from: 0
            to: 1
            duration: 200
        }

        Timer {
            id: toastTimer
            interval: 3500
            onTriggered: {
                toast.visible = false;
                toast.opacity = 0;
            }
        }

        function show(msg, lvl) {
            toast.message = msg;
            toast.level = lvl || "info";
            toast.visible = true;
            toastAnim.restart();
            toastTimer.restart();
        }
    }
}
