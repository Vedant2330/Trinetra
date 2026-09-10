import SwiftUI
import AppKit

public struct HermesDrawerView: View {
    @Environment(AppState.self) private var state

    @State private var inputPrompt: String = ""

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            // Header Bar
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(Color.accentColor.opacity(0.15))
                        .frame(width: 32, height: 32)
                    Image(systemName: "sparkles")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Color.accentColor)
                }

                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text("TRINETRACHAT")
                            .font(.system(size: 13, weight: .bold, design: .monospaced))
                        Text("COPILOT")
                            .font(.system(size: 9, weight: .heavy, design: .monospaced))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1.5)
                            .background(Color.accentColor)
                            .clipShape(RoundedRectangle(cornerRadius: 3))
                    }

                    HStack(spacing: 4) {
                        Circle()
                            .fill(state.hermesStatus?.available == true ? Color.green : Color.orange)
                            .frame(width: 6, height: 6)
                        Text(state.hermesStatus?.available == true ? "Online • Deterministic Grounding" : "Offline / 503 Gate")
                            .font(.system(size: 10))
                            .foregroundStyle(state.hermesStatus?.available == true ? .green : .secondary)
                    }
                }

                Spacer()

                // Clear / New Chat Button
                Button {
                    state.clearHermesChat()
                } label: {
                    Image(systemName: "trash")
                        .font(.system(size: 12))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .help("Clear Chat / New Inquiry")

                // Explicit Close Button
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        state.isHermesDrawerOpen = false
                    }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .help("Close Copilot Drawer (Esc)")
                .keyboardShortcut(.cancelAction)
            }
            .padding(14)
            .background(Color(NSColor.windowBackgroundColor))
            .overlay(Divider(), alignment: .bottom)

            // Chat Messages Scroll
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        if state.hermesMessages.isEmpty {
                            VStack(spacing: 14) {
                                Image(systemName: "brain.head.profile")
                                    .font(.system(size: 38))
                                    .foregroundStyle(Color.accentColor)
                                    .padding(.top, 24)

                                Text("TRINETRA Grounded Clip Intelligence")
                                    .font(.system(size: 14, weight: .bold))

                                Text("Inquire about events, people counts, trajectories, and zone violations. All answers are deterministically grounded in database telemetry with zero hallucination.")
                                    .font(.system(size: 11))
                                    .foregroundStyle(.secondary)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 16)

                                // Quick Prompts
                                VStack(spacing: 8) {
                                    QuickPromptButton(
                                        title: "Summarize this clip",
                                        icon: "doc.text.magnifyingglass"
                                    ) {
                                        ask("Summarize this video clip, including total tracks, people, and any notable events.")
                                    }
                                    QuickPromptButton(
                                        title: "What were the most important events?",
                                        icon: "exclamationmark.triangle"
                                    ) {
                                        ask("What were the most important events and critical alerts in this session?")
                                    }
                                    QuickPromptButton(
                                        title: "List all tracks and detections",
                                        icon: "person.2"
                                    ) {
                                        ask("List all unique tracks, classified objects, and their duration in the scene.")
                                    }
                                    QuickPromptButton(
                                        title: "Were there any restricted zone breaches?",
                                        icon: "shield.slash"
                                    ) {
                                        ask("Were there any restricted zone breaches or anomalous trajectory behaviors?")
                                    }
                                }
                                .padding(.top, 12)
                            }
                            .padding(.horizontal, 16)
                            .frame(maxWidth: .infinity)
                        } else {
                            ForEach(state.hermesMessages) { msg in
                                HermesMessageBubble(message: msg)
                                    .id(msg.id)
                            }

                            if state.isHermesThinking {
                                HStack(spacing: 8) {
                                    ProgressView()
                                        .controlSize(.small)
                                    Text("Reasoning over verified session facts...")
                                        .font(.system(size: 11, design: .monospaced))
                                        .foregroundStyle(.secondary)
                                }
                                .padding(10)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }
                    }
                    .padding(14)
                }
                .onChange(of: state.hermesMessages.count) {
                    if let last = state.hermesMessages.last {
                        withAnimation {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }

            // Bottom Input Bar
            VStack(spacing: 8) {
                Divider()
                HStack(spacing: 8) {
                    TextField("Ask TRINETRACHAT about this session...", text: $inputPrompt)
                        .textFieldStyle(.plain)
                        .padding(8)
                        .background(Color(NSColor.controlBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .onSubmit {
                            submitPrompt()
                        }

                    Button {
                        submitPrompt()
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 22))
                            .foregroundStyle(Color.accentColor)
                    }
                    .buttonStyle(.plain)
                    .disabled(inputPrompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || state.isHermesThinking)
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
            }
            .background(Color(NSColor.windowBackgroundColor))
        }
    }

    private func submitPrompt() {
        let text = inputPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputPrompt = ""
        ask(text)
    }

    private func ask(_ text: String) {
        state.askHermes(prompt: text)
    }
}

// MARK: - Message Bubble

struct HermesMessageBubble: View {
    let message: HermesChatMessage

    var body: some View {
        VStack(alignment: message.isUser ? .trailing : .leading, spacing: 6) {
            // Role & Latency Tag
            HStack(spacing: 6) {
                if message.isUser {
                    Spacer()
                    Text("OPERATOR")
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundStyle(.secondary)
                } else {
                    HStack(spacing: 4) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 9))
                            .foregroundStyle(Color.accentColor)
                        Text("TRINETRACHAT")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundStyle(Color.accentColor)
                    }

                    if let lat = message.latencyMs {
                        Text("• \(String(format: "%.1f", lat)) ms")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
            }

            // Message Body
            VStack(alignment: .leading, spacing: 8) {
                Text(message.text)
                    .font(.system(size: 12))
                    .foregroundStyle(message.isError ? .red : .primary)
                    .textSelection(.enabled)

                // Taxonomy Count Chips
                let counts = message.taxonomyCounts
                if !counts.isEmpty {
                    HStack(spacing: 6) {
                        if let obs = counts["OBSERVED"], obs > 0 {
                            TaxonomyPill(tag: "OBSERVED", count: obs, color: .green)
                        }
                        if let der = counts["DERIVED"], der > 0 {
                            TaxonomyPill(tag: "DERIVED", count: der, color: .blue)
                        }
                        if let inf = counts["INFERRED"], inf > 0 {
                            TaxonomyPill(tag: "INFERRED", count: inf, color: .orange)
                        }
                    }
                    .padding(.top, 4)
                }
            }
            .padding(10)
            .background(
                message.isUser
                    ? Color.accentColor.opacity(0.18)
                    : (message.isError ? Color.red.opacity(0.1) : Color(NSColor.controlBackgroundColor))
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(
                        message.isUser
                            ? Color.accentColor.opacity(0.3)
                            : (message.isError ? Color.red.opacity(0.3) : Color.secondary.opacity(0.15)),
                        lineWidth: 1
                    )
            )
        }
        .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
    }
}

// MARK: - Taxonomy Pill

struct TaxonomyPill: View {
    let tag: String
    let count: Int
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 5, height: 5)
            Text("[\(tag)]: \(count)")
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundStyle(color)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(color.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

// MARK: - Quick Prompt Button

struct QuickPromptButton: View {
    let title: String
    var icon: String = "bubble.left"
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                    .foregroundStyle(Color.accentColor)
                Text(title)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.primary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(NSColor.controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}
