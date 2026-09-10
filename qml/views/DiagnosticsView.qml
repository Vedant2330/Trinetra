import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".."

Item {
    id: root

    property var healthData: bridge ? bridge.getSystemHealth() : ({})

    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            if (bridge) root.healthData = bridge.getSystemHealth();
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 16

        // Header
        Rectangle {
            Layout.fillWidth: true
            height: 48
            radius: Theme.radius
            color: Theme.surfaceCard
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 12

                Text {
                    text: "SYSTEM TELEMETRY & HARDWARE DIAGNOSTICS"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeSm
                    font.bold: true
                    color: Theme.text
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    height: 22
                    radius: 3
                    width: healthPill.implicitWidth + 12
                    color: (root.healthData && root.healthData.status === "ok") ? Theme.successBg : Theme.dangerBg

                    Text {
                        id: healthPill
                        anchors.centerIn: parent
                        text: (root.healthData && root.healthData.status) ? root.healthData.status.toUpperCase() : "SYSTEM HEALTH OK"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeXs
                        font.bold: true
                        color: (root.healthData && root.healthData.status === "ok") ? Theme.success : Theme.danger
                    }
                }
            }
        }

        // Diagnostics Cards Grid
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16
            rowSpacing: 16

            // Card 1: Vision Pipeline & Models
            Rectangle {
                Layout.fillWidth: true
                height: 180
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    Text {
                        text: "🧠 NEURAL VISION PIPELINE"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.accent
                    }

                    Text {
                        text: "Primary Detector: YOLOv8s (640x640 ONNX Runtime)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Face Detector: YuNet (320x320 ONNX Runtime)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Re-ID Model: Fast-ReID MobileNetV2 (512-D L2 Embeddings)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "ANPR Engine: " + (bridge ? bridge.anprMode.toUpperCase() : "OFF")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                    }
                }
            }

            // Card 2: Zero-Copy Desktop Engine
            Rectangle {
                Layout.fillWidth: true
                height: 180
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    Text {
                        text: "⚡ ZERO-COPY RENDERING ENGINE"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.accent
                    }

                    Text {
                        text: "Rendering Subsystem: Qt Quick 2.15 / PySide6 Native"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Memory Pipeline: QQuickImageProvider (LatestFrameSlot zero-copy)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Active FPS: " + (bridge ? bridge.currentFps.toFixed(1) : "0.0") + " FPS"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.success
                    }

                    Text {
                        text: "Thread Isolation: Global QThreadPool for Hermes reasoning"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                    }
                }
            }

            // Card 3: SQLite Persistence Engine
            Rectangle {
                Layout.fillWidth: true
                height: 180
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    Text {
                        text: "💾 DETERMINISTIC SQLITE PERSISTENCE"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.accent
                    }

                    Text {
                        text: "Database WAL Mode: ENABLED (Zero lock contention)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Background Writer: EventWriter Queue (10k items / retry engine)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Buffered Events: " + (bridge ? bridge.eventsList.length : 0) + " cached in UI"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                    }
                }
            }

            // Card 4: Hermes Grounded AI Gateway
            Rectangle {
                Layout.fillWidth: true
                height: 180
                radius: Theme.radius
                color: Theme.surfaceCard
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    Text {
                        text: "🤖 P-HERMES AI GATEWAY"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        color: Theme.accent
                    }

                    Text {
                        text: "Endpoint: http://127.0.0.1:20128/v1"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Model Target: auto/glm (or auto-discovered local LLM)"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                    }

                    Text {
                        text: "Discipline: Strict [OBSERVED], [DERIVED], [INFERRED] grounding"
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.textSecondary
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
