import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

Rectangle {
    id: root
    color: Theme.surface
    border.color: Theme.border
    border.width: 1

    property string targetEventId: ""
    property var messages: []

    Connections {
        target: bridge
        function onHermesAnswerReceived(result) {
            var msgList = root.messages.slice();
            msgList.push({
                sender: "hermes",
                answer: result.answer,
                status: result.status,
                eventId: result.event_id || "",
                model: result.model || "glm",
                ts: new Date().toLocaleTimeString()
            });
            root.messages = msgList;
        }

        function onHermesErrorOccurred(err) {
            var msgList = root.messages.slice();
            msgList.push({
                sender: "system",
                error: true,
                status: err.status,
                detail: err.detail || "Hermes reasoning engine unreachable.",
                retryable: err.retryable,
                ts: new Date().toLocaleTimeString()
            });
            root.messages = msgList;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                width: 24
                height: 24
                radius: 4
                color: Theme.primaryMuted

                Text {
                    anchors.centerIn: parent
                    text: "⚡"
                    font.pixelSize: 12
                }
            }

            Text {
                text: "TRINETRA INTELLIGENCE ASSISTANT"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSizeSm
                font.bold: true
                color: Theme.text
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                height: 20
                radius: 3
                width: statusTxt.implicitWidth + 12
                color: bridge && bridge.isHermesThinking ? Theme.warningBg : Theme.surfaceHover

                Text {
                    id: statusTxt
                    anchors.centerIn: parent
                    text: bridge && bridge.isHermesThinking ? "THINKING..." : "READY"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: bridge && bridge.isHermesThinking ? Theme.warning : Theme.textSecondary
                }
            }
        }

        // Active Event Filter Indicator
        Rectangle {
            Layout.fillWidth: true
            height: 26
            radius: Theme.radiusSm
            color: root.targetEventId ? Theme.primaryMuted : Theme.surfaceCard
            border.color: root.targetEventId ? Theme.primary : Theme.border
            visible: root.targetEventId !== ""

            RowLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 6

                Text {
                    text: "Scoped to Event: " + root.targetEventId
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.text
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "✕ Clear"
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSizeXs
                    color: Theme.textSecondary
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.targetEventId = ""
                    }
                }
            }
        }

        // Quick Preset Prompts
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Button {
                text: "📊 Summarize Incident Log"
                font.pixelSize: Theme.fontSizeXs
                Layout.fillWidth: true
                onClicked: root.sendPrompt("Summarize all security incidents and perimeter violations observed in the database.")
            }

            Button {
                text: "👤 Cross-Camera Re-ID"
                font.pixelSize: Theme.fontSizeXs
                Layout.fillWidth: true
                onClicked: root.sendPrompt("Audit cross-camera identity appearances and list all global person IDs matching multi-camera detections.")
            }
        }

        // Message History List
        ListView {
            id: chatList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: root.messages

            onCountChanged: {
                Qt.callLater(function() {
                    chatList.positionViewAtEnd();
                });
            }

            delegate: Rectangle {
                width: chatList.width
                height: msgCol.implicitHeight + 16
                radius: Theme.radius
                color: modelData.error ? Theme.dangerBg : (modelData.sender === "user" ? Theme.surfaceElevated : Theme.surfaceCard)
                border.color: modelData.error ? Theme.danger : Theme.border
                border.width: 1

                ColumnLayout {
                    id: msgCol
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: modelData.sender === "user" ? "USER INQUIRY" : (modelData.error ? "HERMES SYSTEM ERROR (503)" : "HERMES AI (" + (modelData.model || "glm") + ")")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs - 1
                            font.bold: true
                            color: modelData.error ? Theme.danger : (modelData.sender === "user" ? Theme.primaryLight : Theme.accent)
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: modelData.ts || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSizeXs - 1
                            color: Theme.textMuted
                        }
                    }

                    Text {
                        text: modelData.error ? (modelData.detail || "Service unavailable") : (modelData.sender === "user" ? modelData.question : formatHermesAnswer(modelData.answer))
                        font.family: modelData.sender === "user" ? Theme.fontSans : Theme.fontMono
                        font.pixelSize: Theme.fontSizeSm
                        color: Theme.text
                        wrapMode: Text.Wrap
                        textFormat: Text.RichText
                        Layout.fillWidth: true
                    }
                }
            }
        }

        // Input Area
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                id: inputField
                Layout.fillWidth: true
                placeholderText: "Ask Hermes grounded in SQLite facts..."
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSizeSm
                color: Theme.text
                background: Rectangle {
                    color: Theme.surfaceElevated
                    radius: Theme.radiusSm
                    border.color: inputField.activeFocus ? Theme.primary : Theme.border
                }

                onAccepted: root.submitInput()
            }

            Button {
                text: "Send"
                enabled: inputField.text.trim().length > 0 && (!bridge || !bridge.isHermesThinking)
                onClicked: root.submitInput()
            }
        }
    }

    function sendPrompt(q) {
        if (!bridge) return;
        var msgList = root.messages.slice();
        msgList.push({
            sender: "user",
            question: q,
            ts: new Date().toLocaleTimeString()
        });
        root.messages = msgList;
        bridge.askHermes(q, root.targetEventId, "", "");
    }

    function submitInput() {
        var text = inputField.text.trim();
        if (text.length === 0) return;
        inputField.text = "";
        sendPrompt(text);
    }

    function formatHermesAnswer(raw) {
        if (!raw) return "";
        var esc = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        // Colorize grounded tag tokens
        esc = esc.replace(/\[OBSERVED\]/g, "<font color='#10b981'><b>[OBSERVED]</b></font>");
        esc = esc.replace(/\[DERIVED\]/g, "<font color='#06b6d4'><b>[DERIVED]</b></font>");
        esc = esc.replace(/\[INFERRED\]/g, "<font color='#f59e0b'><b>[INFERRED]</b></font>");
        return esc.replace(/\n/g, "<br/>");
    }

    function setScopedEvent(evId) {
        root.targetEventId = evId;
    }
}
