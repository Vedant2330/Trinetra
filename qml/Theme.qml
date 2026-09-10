import QtQuick

pragma Singleton

QtObject {
    // --- Palette ---
    readonly property color background: "#F8F9FA"  // warm off-white
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceCard: "#FFFFFF"
    readonly property color surfaceElevated: "#FFFFFF"
    readonly property color surfaceHover: "#F1F5F9"

    readonly property color border: "#E2E8F0"
    readonly property color borderHighlight: "#CBD5E1"
    readonly property color borderActive: "#3B82F6"

    readonly property color primary: "#0F172A" // deep charcoal nav
    readonly property color primaryHover: "#1E293B"
    readonly property color primaryLight: "#475569"
    readonly property color primaryMuted: "#F1F5F9" // light background for active elements

    readonly property color accent: "#3B82F6"
    readonly property color accentHover: "#2563EB"

    readonly property color success: "#10B981"
    readonly property color successBg: "#D1FAE5"

    readonly property color warning: "#F59E0B"
    readonly property color warningBg: "#FEF3C7"

    readonly property color danger: "#EF4444"
    readonly property color dangerBg: "#FEE2E2"

    readonly property color critical: "#DC2626"
    readonly property color criticalBg: "#FECACA"

    readonly property color info: "#3B82F6"

    readonly property color text: "#0F172A" // deep charcoal
    readonly property color textSecondary: "#64748B" // muted slate
    readonly property color textMuted: "#94A3B8"
    readonly property color textDim: "#CBD5E1"

    readonly property color navBackground: "#0F172A" // Deep navy/charcoal for left rail
    readonly property color navText: "#F8FAFC" // White text on dark nav
    readonly property color navTextMuted: "#94A3B8"

    // --- Typography ---
    readonly property string fontSans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif"
    readonly property string fontMono: "Menlo, Monaco, Consolas, 'JetBrains Mono', 'Courier New', monospace"

    readonly property int fontSizeXs: 11
    readonly property int fontSizeSm: 13
    readonly property int fontSizeBase: 14
    readonly property int fontSizeMd: 16
    readonly property int fontSizeLg: 18
    readonly property int fontSizeXl: 22
    readonly property int fontSize2Xl: 26

    // --- Sizing & Radii ---
    readonly property int radiusSm: 4
    readonly property int radius: 6
    readonly property int radiusLg: 8
    readonly property int radiusFull: 9999

    // --- Helpers ---
    function severityColor(sev) {
        if (!sev) return textSecondary;
        var s = sev.toUpperCase();
        if (s === "CRITICAL") return critical;
        if (s === "HIGH") return danger;
        if (s === "MEDIUM" || s === "AMBER") return warning;
        if (s === "LOW" || s === "INFO") return info;
        if (s === "GREEN" || s === "NORMAL") return success;
        return textSecondary;
    }

    function severityBg(sev) {
        if (!sev) return "#F1F5F9";
        var s = sev.toUpperCase();
        if (s === "CRITICAL") return criticalBg;
        if (s === "HIGH") return dangerBg;
        if (s === "MEDIUM" || s === "AMBER") return warningBg;
        if (s === "LOW" || s === "INFO") return "#DBEAFE"; // info bg
        if (s === "GREEN" || s === "NORMAL") return successBg;
        return "#F1F5F9";
    }
}
