import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import CNTheme

// A menu row: check mark or icon column, text, the shortcut right-aligned in
// muted text, a chevron for submenus. Hover = neutral highlight.
T.MenuItem {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Theme.menuItemHeight
    leftPadding: Theme.gap2; rightPadding: Theme.gap2
    hoverEnabled: true
    font: Theme.font
    icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
    // Without a shortcut, a `keyHint` the item may declare (AppMenuBar's
    // KeyHintItem: Tab, Insert, the text's own keys that can't be window
    // shortcuts) shows in its place.
    readonly property string shortcutText: {
        if (control.action && control.action.shortcut) return String(control.action.shortcut)
        var name = "keyHint"
        return control[name] || ""
    }
    readonly property color fg: enabled ? Theme.text : Theme.disabled
    contentItem: Item {
        readonly property int markWidth: Theme.iconSmall + Theme.gap2
        implicitHeight: label.implicitHeight
        implicitWidth: markWidth + label.implicitWidth + (sc.text !== "" ? Theme.px(7) + sc.implicitWidth : 0)
                       + (control.subMenu ? Theme.px(5) : 0)
        Item {
            width: Theme.iconSmall; height: Theme.iconSmall
            anchors.verticalCenter: parent.verticalCenter
            PixelIcon {
                anchors.centerIn: parent
                visible: control.checkable && control.checked
                name: "check"
                size: Theme.iconSmall
                color: Theme.accent
            }
            PixelIcon {
                anchors.centerIn: parent
                visible: !control.checkable && control.icon.source.toString() !== ""
                iconSource: control.icon.source
                size: Theme.iconSmall
                color: control.enabled ? (control.icon.color.a > 0 ? control.icon.color : Theme.icon) : Theme.disabled
            }
        }
        MnemonicLabel {
            id: label
            transform: SnapTranslate { target: label }
            mnemonicVisible: false
            x: parent.markWidth
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            font: control.font
            color: control.fg
        }
        SText {
            id: sc
            anchors.right: parent.right
            anchors.rightMargin: control.subMenu ? Theme.px(5) : 0
            anchors.verticalCenter: parent.verticalCenter
            text: control.shortcutText
            font: Theme.fontS
            color: control.enabled ? Theme.muted : Theme.disabled
        }
    }
    arrow: ChevronIcon {
        direction: "right"
        x: control.width - width - Theme.gap1
        y: (control.height - height) / 2
        visible: control.subMenu
    }
    indicator: Item { }
    background: Rectangle {
        implicitWidth: Theme.px(48)
        radius: Theme.radiusSmall
        color: control.down ? Theme.pressed : control.highlighted && control.enabled ? Theme.selectedRow : "transparent"
    }
}
