import QtQuick
import CNTheme

// The directive hover card (the mockup's HintCard.qml), drawn inside the
// text just under the directive so it scrolls with it. `hint` is
// EditorBridge.hintAt's answer: the reason first (red with a stripe for an
// invalid directive, muted for one that has no effect), then the syntax, one
// line per directive. The mockup's title line has no text in the core yet,
// so it is left out.
Rectangle {
    id: card
    objectName: "hintCard"
    property var hint: ({})
    readonly property string message: hint.message || ""
    readonly property bool bad: message !== "" && !hint.redundant
    readonly property real maxText: Theme.px(115) - 2 * Theme.gap3
    width: Math.min(Theme.px(115), col.implicitWidth + 2 * Theme.gap3)
    height: col.implicitHeight + 2 * Theme.gap2
    radius: Theme.radiusPopup
    color: Theme.popup
    border.width: Theme.hairline
    border.color: bad ? Theme.alpha(Theme.error, 0.7) : Theme.border
    z: 10
    Rectangle {
        z: -1; y: Theme.px(0.75); width: parent.width; height: parent.height
        radius: parent.radius; color: Theme.shadow
    }
    Rectangle { // the error stripe on the left
        visible: card.bad
        x: Theme.hairline; y: Theme.px(1.5); width: Theme.px(0.75); height: parent.height - 2 * y
        radius: width / 2; color: Theme.error
    }
    Column {
        id: col
        x: Theme.gap3; y: Theme.gap2
        spacing: Theme.gap1
        SText {
            objectName: "hintCardMessage"
            visible: card.message !== ""
            text: card.message
            width: Math.min(implicitWidth, card.maxText)
            wrapMode: Text.Wrap
            font: Theme.fontStrong
            color: card.bad ? Theme.error : Theme.muted
        }
        SText {
            objectName: "hintCardSyntax"
            // Wrapped between the examples, never inside one ("{bpm:" / "reset}").
            text: (card.hint.syntax || "").replace(/: /g, ":\u00a0")
            width: Math.min(implicitWidth, card.maxText)
            wrapMode: Text.Wrap
            font: Theme.fontMonoS
            color: Theme.directive
        }
    }
}
