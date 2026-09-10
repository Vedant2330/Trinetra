import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Item {
    id: root

    property int frameCounter: 0
    property string activeSource: bridge ? bridge.activeSourceId : "local"
    property bool isDrawingZone: false
    property string drawingZoneKind: "polygon" // "polygon" or "line"
    property var currentPoints: []

    signal zoneCreated(string name, string kind, var points)

    Connections {
        target: bridge
        function onFrameUpdated() {
            root.frameCounter++;
        }
        function onSessionStateChanged(st) {
            // refresh display
        }
    }

    // Background Container
    Rectangle {
        anchors.fill: parent
        color: Theme.background
        radius: Theme.radiusLg
        border.color: Theme.border
        border.width: 1
        clip: true

        // Video Frame
        Image {
            id: videoFrame
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            asynchronous: false
            cache: false
            source: "image://trinetra/live?" + root.frameCounter
        }

        // Zone Canvas Overlay for rendering and interactive drawing
        Canvas {
            id: zoneCanvas
            anchors.fill: parent

            property var zones: bridge ? bridge.getZones("") : []

            Connections {
                target: bridge
                function onZonesUpdated(newZones) {
                    zoneCanvas.zones = newZones;
                    zoneCanvas.requestPaint();
                }
            }

            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);

                // Draw existing zones
                if (zones && zones.length > 0) {
                    for (var i = 0; i < zones.length; i++) {
                        var z = zones[i];
                        if (!z.points || z.points.length < 2) continue;

                        ctx.beginPath();
                        var p0 = z.points[0];
                        ctx.moveTo(p0[0] * width, p0[1] * height);

                        for (var j = 1; j < z.points.length; j++) {
                            var p = z.points[j];
                            ctx.lineTo(p[0] * width, p[1] * height);
                        }

                        if (z.kind === "polygon") {
                            ctx.closePath();
                            ctx.fillStyle = z.color ? z.color + "33" : "rgba(6, 182, 212, 0.2)";
                            ctx.fill();
                        }

                        ctx.strokeStyle = z.color ? z.color : "#06b6d4";
                        ctx.lineWidth = 2;
                        ctx.stroke();

                        // Label
                        ctx.fillStyle = z.color ? z.color : "#06b6d4";
                        ctx.font = "11px monospace";
                        ctx.fillText(z.name + " (" + z.type + ")", p0[0] * width + 4, p0[1] * height - 4);
                    }
                }

                // Draw in-progress zone
                if (root.isDrawingZone && root.currentPoints.length > 0) {
                    ctx.beginPath();
                    var fp = root.currentPoints[0];
                    ctx.moveTo(fp[0] * width, fp[1] * height);

                    for (var k = 1; k < root.currentPoints.length; k++) {
                        var cp = root.currentPoints[k];
                        ctx.lineTo(cp[0] * width, cp[1] * height);
                    }

                    if (root.drawingZoneKind === "polygon" && root.currentPoints.length > 2) {
                        ctx.closePath();
                        ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
                        ctx.fill();
                    }

                    ctx.strokeStyle = "#ef4444";
                    ctx.lineWidth = 2;
                    ctx.setLineDash([4, 4]);
                    ctx.stroke();
                    ctx.setLineDash([]);

                    // Draw vertices
                    for (var m = 0; m < root.currentPoints.length; m++) {
                        var vp = root.currentPoints[m];
                        ctx.beginPath();
                        ctx.arc(vp[0] * width, vp[1] * height, 4, 0, 2 * Math.PI);
                        ctx.fillStyle = "#ffffff";
                        ctx.fill();
                        ctx.strokeStyle = "#ef4444";
                        ctx.stroke();
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                enabled: root.isDrawingZone
                cursorShape: root.isDrawingZone ? Qt.CrossCursor : Qt.ArrowCursor

                onClicked: function(mouse) {
                    if (!root.isDrawingZone) return;
                    var normX = mouse.x / zoneCanvas.width;
                    var normY = mouse.y / zoneCanvas.height;
                    var newPts = root.currentPoints.slice();
                    newPts.push([normX, normY]);
                    root.currentPoints = newPts;
                    zoneCanvas.requestPaint();
                }

                onDoubleClicked: function(mouse) {
                    if (!root.isDrawingZone) return;
                    root.finishDrawing();
                }
            }
        }

        // Top HUD Bar
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 42
            color: Theme.surfaceHover
            border.color: Theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 16

                // Live indicator
                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: bridge && bridge.sessionStatus === "running" ? Theme.success : Theme.danger
                }

                Text {
                    text: bridge ? bridge.sessionStatus.toUpperCase() : "DISCONNECTED"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    font.bold: true
                    color: bridge && bridge.sessionStatus === "running" ? Theme.success : Theme.textMuted
                }

                Rectangle { width: 1; height: 20; color: Theme.border }

                Text {
                    text: "SOURCE: " + (bridge ? bridge.activeSourceId : "none")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.text
                }

                Rectangle { width: 1; height: 20; color: Theme.border }

                Text {
                    text: "FPS: " + (bridge ? bridge.currentFps.toFixed(1) : "0.0")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.text
                }

                Rectangle { width: 1; height: 20; color: Theme.border }

                Text {
                    text: "ACTIVE TRACKS: " + (bridge ? bridge.activeTracksCount : 0)
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.text
                }

                Item { Layout.fillWidth: true }

                // In-progress zone drawing controls
                RowLayout {
                    visible: root.isDrawingZone
                    spacing: 8

                    Text {
                        text: "Drawing " + root.drawingZoneKind.toUpperCase() + " (" + root.currentPoints.length + " pts)"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs
                        color: Theme.warning
                    }

                    Button {
                        text: "Done"
                        height: 28
                        onClicked: root.finishDrawing()
                    }

                    Button {
                        text: "Cancel"
                        height: 28
                        onClicked: root.cancelDrawing()
                    }
                }
            }
        }

        // Bottom Layer HUD Bar
        LayerTogglesBar {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
        }
    }

    function startDrawing(kind) {
        root.drawingZoneKind = kind;
        root.currentPoints = [];
        root.isDrawingZone = true;
        zoneCanvas.requestPaint();
    }

    function finishDrawing() {
        if (root.currentPoints.length >= (root.drawingZoneKind === "polygon" ? 3 : 2)) {
            var zoneName = "Zone_" + Math.floor(Math.random() * 900 + 100);
            if (bridge) {
                bridge.addZone(zoneName, "RESTRICTED", root.drawingZoneKind, root.currentPoints, "#ef4444");
            }
            root.zoneCreated(zoneName, root.drawingZoneKind, root.currentPoints);
        }
        root.isDrawingZone = false;
        root.currentPoints = [];
        zoneCanvas.requestPaint();
    }

    function cancelDrawing() {
        root.isDrawingZone = false;
        root.currentPoints = [];
        zoneCanvas.requestPaint();
    }
}
