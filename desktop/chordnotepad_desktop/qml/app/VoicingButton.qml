import QtQuick
import QtQuick.Controls
import CNTheme

// Voicing ⌄ with its menu: the player bar's and the Edit chord-sheet
// header's (plan steps E3 and E4). The label is the VoicingMenuState's
// selected voicing, shortened ("Guitar (Standard)" without the tuning's
// notes). While a song plays the button is disabled, so its tooltip with
// the reason hangs off this wrapper, which stays enabled (pitfall 16).
Item {
    id: vb
    required property var store
    // The button's objectName (the tests and the two places tell them apart).
    property string buttonName: "voicingButton"
    property alias menuName: menu.objectName
    property bool showText: true
    // What the label adds to the width when shown (FlatDrop.textWidth).
    readonly property real textWidth: btn.textWidth
    // The sheet header's smaller button, whose menu opens above it, right-aligned.
    property bool compact: false
    signal editVoicings()

    readonly property var vm: vb.store.states.VoicingMenuState
    readonly property string lockedReason: vb.vm.locked_reason || ""
    readonly property string label: {
        for (var g of vb.vm.groups || [])
            for (var c of g) if (c.value === vb.vm.selected) return c.label
        return ""
    }

    implicitWidth: btn.implicitWidth
    implicitHeight: btn.implicitHeight
    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered && !menu.visible
    ToolTip.delay: 600
    ToolTip.text: "Voicing: " + vb.label + (vb.lockedReason ? " (" + vb.lockedReason + ")" : "") + "\n"
                  + "How each chord's notes are chosen: which notes sound, in which octaves,"
                  + " and on a fretted instrument, which shape you play."

    FlatDrop {
        id: btn
        objectName: vb.buttonName
        anchors.fill: parent
        implicitHeight: vb.compact ? Theme.controlSmall : Theme.playerControl
        iconSize: vb.compact ? Theme.iconSmall : Theme.playerIcon
        iconName: "music"
        text: vb.label.replace(/ - [A-G]+\)/, ")")
        showText: vb.showText
        maxTextWidth: Theme.px(30)
        enabled: vb.lockedReason === ""
        checked: menu.visible
        onClicked: {
            if (vb.compact)
                menu.popup(btn, btn.width - menu.implicitWidth, -menu.implicitHeight - Theme.gap1)
            else
                menu.popup(btn, 0, btn.height + Theme.gap1)
        }
    }
    VoicingMenu { id: menu; store: vb.store; onEditVoicings: vb.editVoicings() }
}
