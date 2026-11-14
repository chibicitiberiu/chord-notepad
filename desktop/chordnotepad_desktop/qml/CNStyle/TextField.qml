import QtQuick
import QtQuick.Templates as T
import CNTheme

// Boxed field (no underline): hairline border, accent border + ring on focus.
T.TextField {
    id: control
    implicitWidth: implicitBackgroundWidth || Math.max(contentWidth + leftPadding + rightPadding, Theme.px(40))
    implicitHeight: Theme.controlHeight
    leftPadding: Theme.padX; rightPadding: Theme.padX
    hoverEnabled: true
    font: Theme.font
    color: enabled ? Theme.text : Theme.disabled
    placeholderTextColor: Theme.muted
    selectionColor: Theme.selection
    selectedTextColor: Theme.text
    verticalAlignment: TextInput.AlignVCenter
    SText {
        x: control.leftPadding; height: control.height
        verticalAlignment: Text.AlignVCenter
        visible: !control.length && !control.preeditText
        text: control.placeholderText
        font: control.font
        color: control.placeholderTextColor
        elide: Text.ElideRight
        width: control.width - control.leftPadding - control.rightPadding
    }
    background: Rectangle {
        implicitWidth: Theme.px(40)
        radius: Theme.radius
        color: Theme.input
        border.width: Theme.hairline
        border.color: control.activeFocus ? Theme.accent : control.hovered ? Theme.muted : Theme.borderStrong
        FocusRing { visible: control.activeFocus }
    }
}
