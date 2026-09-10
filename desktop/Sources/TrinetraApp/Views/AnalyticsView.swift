import SwiftUI
import AppKit

public struct AnalyticsView: View {
    @Environment(AppState.self) private var state

    public init() {}

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header Banner
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Image(systemName: "chart.xyaxis.line")
                            .font(.title)
                            .foregroundStyle(Color.accentColor)
                        Text("Real-Time Telemetry & Computer Vision Analytics")
                            .font(.title2.bold())
                    }
                    Text("Live hardware acceleration metrics, inference throughput, crowd density, and kinematics distribution.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 24)
                .padding(.top, 20)

                // Key Performance Metric Cards
                VStack(alignment: .leading, spacing: 10) {
                    Text("SYSTEM PIPELINE & INFERENCE PERFORMANCE")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 24)

                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                        AnalyticsMetricCard(
                            title: "PIPELINE FPS",
                            value: String(format: "%.1f", state.currentSession?.pipeline_fps ?? 0.0),
                            subtitle: "End-to-end ingestion & render",
                            icon: "gauge.with.needle",
                            accentColor: .green
                        )
                        AnalyticsMetricCard(
                            title: "INFERENCE FPS",
                            value: String(format: "%.1f", state.currentSession?.inference_fps ?? 0.0),
                            subtitle: "YOLOv8 + Pose + Re-ID compute",
                            icon: "cpu",
                            accentColor: .blue
                        )
                        AnalyticsMetricCard(
                            title: "AVG LATENCY",
                            value: "\(String(format: "%.1f", state.currentSession?.avg_latency_ms ?? 0.0)) ms",
                            subtitle: "Frame-to-decision time",
                            icon: "timer",
                            accentColor: .orange
                        )
                        AnalyticsMetricCard(
                            title: "DATABASE QUEUE",
                            value: "\(state.health?.database.queue_depth ?? 0)",
                            subtitle: "SQLite WAL Event Engine",
                            icon: "tray.and.arrow.down.fill",
                            accentColor: .purple
                        )
                    }
                    .padding(.horizontal, 24)
                }

                Divider()
                    .padding(.horizontal, 24)

                // Object & Entity Telemetry Cards
                VStack(alignment: .leading, spacing: 10) {
                    Text("ACTIVE TRACKS & ENTITY POPULATION")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 24)

                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                        AnalyticsMetricCard(
                            title: "TOTAL PEDESTRIANS",
                            value: "\(state.currentSession?.people_detected ?? 0)",
                            subtitle: "\(state.currentSession?.active_people ?? 0) currently in frame",
                            icon: "figure.walk",
                            accentColor: .yellow
                        )
                        AnalyticsMetricCard(
                            title: "TOTAL VEHICLES",
                            value: "\(state.currentSession?.vehicles_detected ?? 0)",
                            subtitle: "\(state.currentSession?.active_vehicles ?? 0) currently in frame",
                            icon: "car.fill",
                            accentColor: .teal
                        )
                        AnalyticsMetricCard(
                            title: "SECURITY EVENTS",
                            value: "\(state.events.count)",
                            subtitle: "\(state.liveAlerts.filter { $0.severity.uppercased() == "CRITICAL" }.count) critical alerts",
                            icon: "exclamationmark.triangle.fill",
                            accentColor: .red
                        )
                        AnalyticsMetricCard(
                            title: "PERSON RE-ID GALLERY",
                            value: "\(state.reidPersons.count)",
                            subtitle: "Unique identity profiles",
                            icon: "person.2.badge.gearshape.fill",
                            accentColor: .pink
                        )
                    }
                    .padding(.horizontal, 24)
                }

                Divider()
                    .padding(.horizontal, 24)

                // Deep Analytics Analytics Status Rows
                VStack(alignment: .leading, spacing: 12) {
                    Text("INTELLIGENCE MODULE STATUS")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 24)

                    VStack(spacing: 8) {
                        AnalyticsStatusRow(
                            moduleName: "YOLOv8 Object Detection & ByteTrack",
                            status: state.isSessionActive ? "Online & Tracking" : "Standby",
                            indicatorColor: state.isSessionActive ? .green : .secondary,
                            detail: "PyTorch MPS Acceleration, 80-class COCO with class filtering"
                        )
                        AnalyticsStatusRow(
                            moduleName: "Human Pose Analytics (17 COCO Keypoints)",
                            status: state.layers.pose ? "Active Analysis" : "Disabled / Off",
                            indicatorColor: state.layers.pose ? .green : .secondary,
                            detail: "YOLOv8-pose skeleton estimation, limb angle kinematics, fall detection"
                        )
                        AnalyticsStatusRow(
                            moduleName: "YuNet Face Landmark Detection",
                            status: state.layers.faces ? "Active Analysis" : "Disabled / Off",
                            indicatorColor: state.layers.faces ? .blue : .secondary,
                            detail: "OpenCV DNN YuNet landmarking with 5 facial keypoints"
                        )
                        AnalyticsStatusRow(
                            moduleName: "Fast-ReID MobileNetV2 Feature Extraction",
                            status: "Online",
                            indicatorColor: .green,
                            detail: "512-dimensional appearance embeddings with cosine similarity distance"
                        )
                        AnalyticsStatusRow(
                            moduleName: "Grounded Hermes 3 AI Reasoner",
                            status: state.hermesStatus?.available == true ? "Available (Zero Hallucination)" : "Offline (503 Honesty Gate)",
                            indicatorColor: state.hermesStatus?.available == true ? .green : .orange,
                            detail: "Structured prompt formatting with deterministic SQLite factual context"
                        )
                    }
                    .padding(.horizontal, 24)
                }
            }
            .padding(.bottom, 32)
        }
    }
}

// MARK: - Metric Card

struct AnalyticsMetricCard: View {
    let title: String
    let value: String
    let subtitle: String
    let icon: String
    let accentColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title)
                    .font(.system(size: 10, weight: .heavy))
                    .foregroundStyle(.secondary)
                Spacer()
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundStyle(accentColor)
            }

            Text(value)
                .font(.system(size: 24, weight: .bold, design: .monospaced))
                .foregroundStyle(.primary)

            Text(subtitle)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
        )
    }
}

// MARK: - Analytics Status Row

struct AnalyticsStatusRow: View {
    let moduleName: String
    let status: String
    let indicatorColor: Color
    let detail: String

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(indicatorColor)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(moduleName)
                    .font(.system(size: 12, weight: .semibold))
                Text(detail)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text(status)
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundStyle(indicatorColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(indicatorColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .padding(12)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}
