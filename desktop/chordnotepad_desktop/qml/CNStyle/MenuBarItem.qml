import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T
import CNTheme

T.MenuBarItem {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Theme.menuBarHeight
    leftPadding: Theme.padX; rightPadding: Theme.padX
    hoverEnabled: true
    font: Theme.font
    contentItem: MnemonicLabel {
        id: mbl
        transform: SnapTranslate { target: mbl }
        mnemonicVisible: false
        text: control.text
        font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        y: Theme.gap1; height: parent.height - 2 * Theme.gap1
        implicitWidth: Theme.px(10)
        radius: Theme.radiusSmall
        color: (control.menu && control.menu.visible) || control.down ? Theme.pressed
               : control.hovered ? Theme.hover : "transparent"
    }
}
