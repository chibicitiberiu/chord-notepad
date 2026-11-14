import QtQuick
import CNStyle
import CNTheme

// A number field of the Settings window: the look of CNStyle's SpinBox (the
// stacked chevrons, the wheel and Up/Down while focused) over a text field
// that keeps whatever is typed. A SpinBox can't hold a value that doesn't
// parse or is out of range (it snaps back, pitfall 20); the form needs to
// keep it, mark it and re-check it on every keystroke, so this sends the
// text as it is (`edited`) and says when to save (`committed`: Enter,
// leaving the field, an arrow).
//
// `shown` is the value to show; it is applied while the field doesn't have
// the focus, so an echo of what is being typed never moves the cursor.
// `error` marks it red and ends its tooltip (`tip`) with "⚠ error".
FormField {
    id: control
    property real from: 0
    property real to: 100
    property real stepSize: 1
    readonly property int decimals: {
        var s = String(control.stepSize)
        var dot = s.indexOf(".")
        return dot < 0 ? 0 : s.length - dot - 1
    }
    readonly property int arrowWidth: Theme.px(4.5)
    rightPadding: arrowWidth + Theme.gap1
    implicitWidth: Theme.px(20)
    horizontalAlignment: TextInput.AlignLeft

    function stepBy(n) {
        var v = parseFloat(control.text)
        if (isNaN(v)) v = Math.min(Math.max(0, control.from), control.to)
        else v = v + n * control.stepSize
        v = Math.min(Math.max(v, control.from), control.to)
        v = Math.round(v / control.stepSize) * control.stepSize
        control.text = control.decimals > 0 ? v.toFixed(control.decimals) : String(Math.round(v))
        control.edited(control.text)
        control.committed()
    }
    Keys.onUpPressed: control.stepBy(1)
    Keys.onDownPressed: control.stepBy(-1)
    WheelHandler {
        enabled: control.activeFocus && control.enabled
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: (event) => control.stepBy(event.angleDelta.y > 0 ? 1 : -1)
    }

    Rectangle {
        objectName: "spinUp"
        x: control.width - width - Theme.hairline
        y: Theme.hairline
        width: control.arrowWidth; height: control.height / 2 - Theme.hairline
        radius: Theme.radiusSmall
        color: upArea.pressed ? Theme.pressed : upArea.containsMouse ? Theme.hover : "transparent"
        PixelIcon { anchors.centerIn: parent; name: "chevron-up"; size: Theme.px(3.5); color: control.enabled ? Theme.icon : Theme.disabled }
        MouseArea { id: upArea; anchors.fill: parent; hoverEnabled: true; enabled: control.enabled; onClicked: control.stepBy(1) }
    }
    Rectangle {
        objectName: "spinDown"
        x: control.width - width - Theme.hairline
        y: control.height / 2
        width: control.arrowWidth; height: control.height / 2 - Theme.hairline
        radius: Theme.radiusSmall
        color: downArea.pressed ? Theme.pressed : downArea.containsMouse ? Theme.hover : "transparent"
        PixelIcon { anchors.centerIn: parent; name: "chevron-down"; size: Theme.px(3.5); color: control.enabled ? Theme.icon : Theme.disabled }
        MouseArea { id: downArea; anchors.fill: parent; hoverEnabled: true; enabled: control.enabled; onClicked: control.stepBy(-1) }
    }
}
