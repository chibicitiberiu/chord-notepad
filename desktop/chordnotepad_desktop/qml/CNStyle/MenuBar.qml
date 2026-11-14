import QtQuick
import QtQuick.Templates as T
import CNTheme

T.MenuBar {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Theme.menuBarHeight
    leftPadding: Theme.gap1
    delegate: MenuBarItem { }
    contentItem: Row {
        spacing: control.spacing
        Repeater { model: control.contentModel }
    }
    background: Rectangle { color: Theme.chrome }
}
