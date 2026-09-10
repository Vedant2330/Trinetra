import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: root

    property string selectedSeverity: "ALL"
    property string searchText: ""
    property var allEvents: bridge ? bridge.eventsList : []

    signal inspectEvent(string eventId)
    signal askHermes(string eventId)

    Connections {
        target: bridge
        function onEventsListUpdated(evs) {
            root.allEvents = evs;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        // Top Filter Bar
        Rectangle {
            Layout.fillWidth: true
            height: 52
            radius: Theme.radius
            color: Theme.surfaceCard
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 10

                Text {
                    text: "SEVERITY FILTER:"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    font.bold: true
                    color: Theme.textMuted
                }

                Repeater {
                    model: ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
                    delegate: Rectangle {
                        height: 28
                        radius: Theme.radiusSm
                        width: sevFilterText.implicitWidth + 16
                        color: root.selectedSeverity === modelData ? Theme.primaryMuted : Theme.surfaceElevated
                        border.color: root.selectedSeverity === modelData ? Theme.primary : Theme.border
                        border.width: 1

                        Text {
                            id: sevFilterText
                            anchors.centerIn: parent
                            text: modelData
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs
                            font.bold: root.selectedSeverity === modelData
                            color: root.selectedSeverity === modelData ? Theme.text : Theme.textSecondary
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.selectedSeverity = modelData
                        }
                    }
                }

                Rectangle { width: 1; height: 20; color: Theme.border }

                TextField {
                    id: searchField
                    Layout.preferredWidth: 240
                    placeholderText: "Search type, zone, source..."
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSizeSm
                    color: Theme.text
                    background: Rectangle {
                        color: Theme.surfaceElevated
                        radius: Theme.radiusSm
                        border.color: searchField.activeFocus ? Theme.primary : Theme.border
                    }
                    onTextChanged: root.searchText = text.toLowerCase()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: "🔄 Refresh DB"
                    font.pixelSize: Theme.fontSizeXs
                    onClicked: {
                        if (bridge) {
                            root.allEvents = bridge.getEventsList(100, 0);
                        }
                    }
                }
            }
        }

        // Events Grid / List
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ListView {
                id: eventsListView
                width: parent.width - 16
                spacing: 8
                model: getFilteredEvents()

                delegate: EventCard {
                    width: eventsListView.width
                    eventData: modelData
                    onInspectRequested: function(evId) {
                        root.inspectEvent(evId);
                    }
                    onAskHermesRequested: function(evId) {
                        root.askHermes(evId);
                    }
                }
            }
        }
    }

    function getFilteredEvents() {
        if (!root.allEvents) return [];
        var res = [];
        for (var i = 0; i < root.allEvents.length; i++) {
            var ev = root.allEvents[i];
            // Severity check
            if (root.selectedSeverity !== "ALL") {
                if (!ev.severity || ev.severity.toUpperCase() !== root.selectedSeverity) {
                    continue;
                }
            }
            // Search text check
            if (root.searchText !== "") {
                var str = ((ev.type || "") + " " + (ev.source_id || "") + " " + (ev.zone_id || "") + " " + (ev.id || "")).toLowerCase();
                if (str.indexOf(root.searchText) === -1) {
                    continue;
                }
            }
            res.push(ev);
        }
        return res;
    }
}
