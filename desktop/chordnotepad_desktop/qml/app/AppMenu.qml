import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The ☰ menu (plan step F1), in Chrome's shape (the mockup's AppMenu.qml):
// a wide menu, the common commands at the top level with their shortcuts,
// the rare ones in submenus, and an inline Zoom row for the whole window's
// scale. The groups:
//   New, Open, Open recent ›, Save, Save as | Zoom − % + ⛶ | Export MIDI |
//   Show menu bar ✓, Dark theme ✓ | Settings | Help › | Quit
// The items are AppActions' (and the editor's) Actions: no shortcut is
// declared here. A second click on ☰ closes it (CloseOnPressOutsideParent:
// the press on ☰ isn't "outside", and the button toggles).
Menu {
    id: root
    objectName: "appMenu"
    required property var actions      // AppActions
    required property var files        // FilesModel (Open recent)
    width: Theme.px(80)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent

    MenuItem { objectName: "appMenuNew"; action: root.actions.newAction }
    MenuItem { action: root.actions.openAction }
    RecentMenu { objectName: "appMenuRecent"; files: root.files }
    MenuItem { action: root.actions.saveAction }
    MenuItem { action: root.actions.saveAsAction }
    MenuSeparator { }

    // Zoom  − 100% +   ⛶
    Item {
        objectName: "appMenuZoom"
        implicitHeight: Theme.menuItemHeight + Theme.gap1
        width: root.availableWidth
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.gap2 + Theme.iconSmall + Theme.gap2
            anchors.rightMargin: Theme.gap1
            spacing: Theme.gap1
            Label { text: "Zoom"; Layout.fillWidth: true }
            Rectangle {
                Layout.preferredHeight: Theme.controlSmall
                Layout.preferredWidth: zrow.implicitWidth
                radius: Theme.radius
                color: "transparent"
                border.width: Theme.hairline; border.color: Theme.border
                Row {
                    id: zrow
                    anchors.centerIn: parent
                    ToolButton {
                        objectName: "scaleOutButton"
                        icon.source: Theme.iconUrl("minus"); icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
                        implicitWidth: Theme.px(8); implicitHeight: Theme.controlSmall - 2 * Theme.hairline; padding: 0
                        enabled: root.actions.scaleDownAction.enabled
                        onClicked: root.actions.scaleDownAction.trigger()
                        ToolTip.visible: hovered; ToolTip.delay: 600; ToolTip.text: "Ctrl+Alt+-"
                    }
                    AbstractButton {
                        id: pct
                        objectName: "scaleResetButton"
                        implicitWidth: Theme.px(12); implicitHeight: Theme.controlSmall - 2 * Theme.hairline
                        hoverEnabled: true
                        onClicked: root.actions.scaleResetAction.trigger()
                        ToolTip.visible: hovered; ToolTip.delay: 600; ToolTip.text: "Reset  Ctrl+Alt+0"
                        background: Rectangle { color: pct.hovered ? Theme.hover : "transparent" }
                        contentItem: SText {
                            objectName: "scalePercent"
                            text: Math.round(Theme.scale * 100) + "%"
                            font: Theme.font; color: Theme.text
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                    }
                    ToolButton {
                        objectName: "scaleInButton"
                        icon.source: Theme.iconUrl("plus"); icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
                        implicitWidth: Theme.px(8); implicitHeight: Theme.controlSmall - 2 * Theme.hairline; padding: 0
                        enabled: root.actions.scaleUpAction.enabled
                        onClicked: root.actions.scaleUpAction.trigger()
                        ToolTip.visible: hovered; ToolTip.delay: 600; ToolTip.text: "Ctrl+Alt+="
                    }
                }
            }
            ToolButton {
                objectName: "fullScreenButton"
                icon.source: Theme.iconUrl("fullscreen"); icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
                implicitWidth: Theme.px(8); implicitHeight: Theme.controlSmall; padding: 0
                onClicked: { root.close(); root.actions.fullScreenAction.trigger() }
                ToolTip.visible: hovered; ToolTip.delay: 600; ToolTip.text: "Full screen  F11"
            }
        }
    }
    MenuSeparator { }
    MenuItem { action: root.actions.exportMidiAction }
    MenuSeparator { }
    MenuItem { objectName: "appMenuMenuBar"; action: root.actions.menuBarAction }
    MenuItem { objectName: "appMenuDark"; action: root.actions.darkAction }
    MenuSeparator { }
    MenuItem { action: root.actions.settingsAction }
    MenuSeparator { }
    Menu {
        objectName: "appMenuHelp"
        title: "&Help"
        MenuItem { action: root.actions.helpAction }
        MenuItem { action: root.actions.quickStartAction }
        MenuItem { action: root.actions.shortcutsAction }
        MenuSeparator { }
        MenuItem { action: root.actions.licencesAction }
        MenuItem { action: root.actions.aboutAction }
    }
    MenuSeparator { }
    MenuItem { objectName: "appMenuQuit"; action: root.actions.quitAction }
}
