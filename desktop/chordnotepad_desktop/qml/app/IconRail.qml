pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme
import CNStyle      // PixelIcon: qmllint misses it through QtQuick.Controls here

// The activity rail (VS Code style, the mockup's): switches the Edit
// sidebar; clicking the active icon collapses it. The Settings gear at the
// bottom. The icons' shortcuts are SidebarActions.qml's.
Rectangle {
    id: rail
    objectName: "iconRail"
    required property var sidebars
    signal openSettings()
    implicitWidth: Theme.railWidth
    color: Theme.chrome
    Rectangle { anchors.right: parent.right; width: Theme.hairline; height: parent.height; color: Theme.border }

    component RailButton: AbstractButton {
        id: b
        property string key
        property string iconName
        property string tip
        property string shortcutHint
        readonly property bool active: rail.sidebars.current === key
        objectName: "rail:" + key
        implicitWidth: Theme.railWidth; implicitHeight: Theme.railWidth
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        checkable: false
        onClicked: rail.sidebars.toggle(b.key)
        ToolTip.visible: hovered; ToolTip.delay: 600
        ToolTip.text: b.tip + (b.shortcutHint ? "  <font color='" + Theme.muted + "'>" + b.shortcutHint + "</font>" : "")
        background: Item {
            Rectangle {   // the active marker, on the outer edge
                visible: b.active
                width: Theme.px(0.5); height: parent.height - 2 * Theme.gap2
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.accent
            }
            Rectangle {   // the keyboard focus
                visible: b.visualFocus
                anchors.fill: parent; anchors.margins: Theme.gap1
                radius: Theme.radiusSmall
                color: "transparent"
                border.width: Theme.hairline; border.color: Theme.accent
            }
        }
        contentItem: Item {
            PixelIcon {
                anchors.centerIn: parent
                name: b.iconName
                size: Theme.iconSize + Theme.gap1
                color: b.active || b.hovered ? Theme.text : Theme.muted
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.rightMargin: Theme.hairline
        spacing: 0
        RailButton {
            key: "directives"; iconName: "braces"
            tip: "Directives"; shortcutHint: "Ctrl+Shift+D"
        }
        RailButton {
            key: "identifier"; iconName: "piano"
            tip: "Chord identifier"; shortcutHint: "Ctrl+Shift+I"
        }
        Item { Layout.fillHeight: true }
        AbstractButton {
            id: gear
            objectName: "rail:settings"
            implicitWidth: Theme.railWidth; implicitHeight: Theme.railWidth
            hoverEnabled: true
            focusPolicy: Qt.TabFocus
            onClicked: rail.openSettings()
            ToolTip.visible: hovered; ToolTip.delay: 600
            ToolTip.text: "Settings (Ctrl+,)"
            contentItem: Item {
                PixelIcon {
                    anchors.centerIn: parent
                    name: "cog"
                    size: Theme.iconSize
                    color: gear.hovered ? Theme.text : Theme.muted
                }
            }
            background: Item { }
        }
    }
}
