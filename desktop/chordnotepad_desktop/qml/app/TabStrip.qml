import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Workspace tabs under the menu bar (MuseScore 4's Home | Score | Publish):
// Edit | Play on the left, the document's name and the unsaved dot on the
// right, then the Chrome-style ☰ (its menu is plan step F1's).
//
// `document` is the session's DocumentState map (display_name, location,
// is_modified). `mode` is "edit" or "play"; a click on a tab asks for the
// other with modeRequested.
Rectangle {
    id: strip
    required property var document
    property string mode: "edit"
    signal modeRequested(string mode)
    signal openAppMenu(Item anchor)
    property alias menuButton: burger
    readonly property bool dirty: strip.document.is_modified === true
    readonly property string name: strip.document.display_name || ""
    implicitHeight: Theme.tabStripHeight
    color: Theme.chrome
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.hairline; color: Theme.border }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.gap2; anchors.rightMargin: Theme.gap1
        spacing: Theme.gap2
        TabBar {
            id: tabs
            objectName: "workspaceTabs"
            Layout.fillHeight: true
            currentIndex: strip.mode === "play" ? 1 : 0
            onCurrentIndexChanged: {
                var wanted = currentIndex === 1 ? "play" : "edit"
                if (wanted !== strip.mode) strip.modeRequested(wanted)
            }
            TabButton {
                objectName: "editTab"
                text: "Edit"; height: parent ? parent.height : implicitHeight
                ToolTip.visible: hovered; ToolTip.delay: 800; ToolTip.text: "Write the song  <font color='" + Theme.muted + "'>Ctrl+1</font>"
            }
            TabButton {
                objectName: "playTab"
                text: "Play"; height: parent ? parent.height : implicitHeight
                ToolTip.visible: hovered; ToolTip.delay: 800; ToolTip.text: "Play along  <font color='" + Theme.muted + "'>Ctrl+2</font>"
            }
        }
        Item { Layout.fillWidth: true }
        Label {
            objectName: "documentName"
            text: strip.name
            font: Theme.fontStrong
            color: Theme.text
            elide: Text.ElideRight
            Layout.maximumWidth: strip.width / 3
            HoverHandler { id: titleHover }
            ToolTip.visible: titleHover.hovered
            ToolTip.delay: 600
            ToolTip.text: (strip.document.location || strip.name) + (strip.dirty ? " · unsaved changes" : "")
        }
        Rectangle {
            objectName: "unsavedDot"
            visible: strip.dirty
            width: Theme.px(1.75); height: width; radius: width / 2
            color: Theme.muted
        }
        Item { Layout.preferredWidth: Theme.gap2 }
        IconButton {   // Chrome-style app menu
            id: burger
            objectName: "appMenuButton"
            iconName: "menu"
            tip: "Menu"
            // The ☰ menu comes with the menus (plan step F1).
            enabled: false
            onClicked: strip.openAppMenu(burger)
        }
    }
}
