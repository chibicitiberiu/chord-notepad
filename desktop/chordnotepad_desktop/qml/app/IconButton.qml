import QtQuick
import QtQuick.Controls
import CNTheme

// Toolbar button: monochrome icon, optional label, tooltip with shortcut.
ToolButton {
    id: control
    property string iconName
    property string tip
    property string shortcutHint
    property bool showLabel: false
    // The button's menu or popup is open: no tooltip over it.
    property bool popupOpen: false
    display: showLabel && text !== "" ? AbstractButton.TextBesideIcon : AbstractButton.IconOnly
    icon.source: iconName ? Theme.iconUrl(iconName) : ""
    focusPolicy: Qt.TabFocus
    ToolTip.visible: hovered && !popupOpen && (tip !== "" || text !== "")
    ToolTip.delay: 600
    ToolTip.text: (tip || text) + (shortcutHint ? "  <font color='" + Theme.muted + "'>" + shortcutHint + "</font>" : "")
}
