import QtQuick
import QtQuick.Controls
import CNTheme

// Instrument ⌄ with its menu: the player bar's and the Edit chord-sheet
// header's, beside Voicing (Tibi, 2026-11-17: "you typically switch both
// together"). The label is InstrumentMenuState's program, named by the
// player bar model (instrumentName: the soundfont's label, tidied).
Item {
    id: ib
    required property var store
    required property var player
    // The button's objectName (the tests and the two places tell them apart).
    property string buttonName: "instrumentButton"
    property alias menuName: menu.objectName
    property bool showText: true
    // What the label adds to the width when shown (FlatDrop.textWidth).
    readonly property real textWidth: btn.textWidth
    // The sheet header's smaller button, whose menu opens above it, right-aligned.
    property bool compact: false

    readonly property var im: ib.store.states.InstrumentMenuState
    readonly property string label: {
        for (var f of ib.im.families || [])
            for (var c of f.items) if (parseInt(c.value) === ib.im.current) return ib.player.instrumentName(c.label)
        return ""
    }
    readonly property alias tip: btn.tip

    implicitWidth: btn.implicitWidth
    implicitHeight: btn.implicitHeight

    FlatDrop {
        id: btn
        objectName: ib.buttonName
        anchors.fill: parent
        implicitHeight: ib.compact ? Theme.controlSmall : Theme.playerControl
        iconSize: ib.compact ? Theme.iconSmall : Theme.playerIcon
        iconName: "guitar-acoustic"
        text: ib.label
        showText: ib.showText
        maxTextWidth: Theme.px(26)
        tip: "Instrument: " + ib.label + " (General MIDI " + ib.im.current + ")\n"
             + "The sound you hear. Which notes play is the voicing's choice."
        checked: menu.visible
        onClicked: {
            if (ib.compact)
                menu.popup(btn, btn.width - menu.implicitWidth, -menu.implicitHeight - Theme.gap1)
            else
                menu.popup(btn, 0, btn.height + Theme.gap1)
        }
    }
    InstrumentMenu { id: menu; store: ib.store }
}
