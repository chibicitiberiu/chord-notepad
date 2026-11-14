import QtQuick
import QtQuick.Templates as T
import CNTheme

// Number field with stacked up/down chevrons (desktop spin box); the wheel
// and arrow keys step too.
// SpinBox holds integers only: a fractional value (a speed, a zoom) is scaled
// to an int with textFromValue/valueFromText, and typed text is committed on
// Enter (pitfall 20).
T.SpinBox {
    id: control
    readonly property int arrowWidth: Theme.px(4.5)
    implicitWidth: Math.max(implicitBackgroundWidth, contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Theme.controlHeight
    leftPadding: Theme.padX
    rightPadding: arrowWidth + Theme.gap1
    editable: true
    wheelEnabled: true
    hoverEnabled: true
    font: Theme.font
    validator: IntValidator { bottom: Math.min(control.from, control.to); top: Math.max(control.from, control.to) }
    contentItem: TextInput {
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
        selectionColor: Theme.selection
        selectByMouse: true
        verticalAlignment: Qt.AlignVCenter
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: control.inputMethodHints
        clip: width < implicitWidth
    }
    up.indicator: Rectangle {
        x: control.width - width - Theme.hairline
        y: Theme.hairline
        width: control.arrowWidth; height: control.height / 2 - Theme.hairline
        radius: Theme.radiusSmall
        color: control.up.pressed ? Theme.pressed : control.up.hovered ? Theme.hover : "transparent"
        ChevronIcon { anchors.centerIn: parent; direction: "up"; size: Theme.px(3.5); color: Theme.icon }
    }
    down.indicator: Rectangle {
        x: control.width - width - Theme.hairline
        y: control.height / 2
        width: control.arrowWidth; height: control.height / 2 - Theme.hairline
        radius: Theme.radiusSmall
        color: control.down.pressed ? Theme.pressed : control.down.hovered ? Theme.hover : "transparent"
        ChevronIcon { anchors.centerIn: parent; direction: "down"; size: Theme.px(3.5); color: Theme.icon }
    }
    background: Rectangle {
        implicitWidth: Theme.px(20)
        radius: Theme.radius
        color: Theme.input
        border.width: Theme.hairline
        border.color: control.activeFocus ? Theme.accent : control.hovered ? Theme.muted : Theme.borderStrong
        FocusRing { visible: control.activeFocus }
    }
}
