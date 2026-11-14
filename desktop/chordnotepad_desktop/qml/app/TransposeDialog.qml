import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Transpose (plan step G2), the mockup's dialog with Tk's texts
// (dialogs/transpose_dialog.py): the scope line says whether the selection
// or the whole song moves, the box takes -11..11 semitones. Enter or
// Transpose applies (`transpose(semitones)`; 0 does nothing), Escape or
// Cancel closes. The session makes it one undo step and says so in the
// status line; a whole-song transpose also moves the key.
AppDialog {
    id: dlg
    objectName: "transposeDialog"
    property bool hasSelection: false
    property string problem: ""
    signal transpose(int semitones)

    function ask(selection) {
        dlg.hasSelection = selection
        dlg.problem = ""
        box.shown = "0"
        box.text = "0"
        dlg.open()
    }
    function apply() {
        var t = box.text.trim()
        var n = /^[+-]?\d+$/.test(t) ? parseInt(t, 10) : NaN
        if (isNaN(n) || n < -11 || n > 11) {
            // Closing with 0 would look like Transpose did nothing (Tk's message).
            dlg.problem = "Enter a whole number of semitones from -11 to 11."
            return
        }
        dlg.close()
        if (n !== 0) dlg.transpose(n)
    }

    title: "Transpose"
    width: Theme.px(118)
    closePolicy: Popup.CloseOnEscape
    onOpened: { box.forceActiveFocus(); box.selectAll() }
    contentItem: ColumnLayout {
        spacing: Theme.gap3
        Label {
            objectName: "transposeScope"
            text: (dlg.hasSelection ? "Transpose selection" : "Transpose whole song") + "."
            font: Theme.fontMedium
            Layout.fillWidth: true
        }
        Label {
            text: "Shift every chord by the chosen number of semitones (positive = up, negative = down)."
            color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        RowLayout {
            spacing: Theme.gap3
            Label { text: "Semitones"; font: Theme.fontMedium; Layout.fillWidth: true }
            FormSpin {
                id: box
                objectName: "transposeSemitones"
                from: -11; to: 11
                shown: "0"
                error: dlg.problem
                Layout.preferredWidth: Theme.px(22)
                // What is typed stays when the focus goes to a button.
                onEdited: (t) => { dlg.problem = ""; box.shown = t }
                Keys.onReturnPressed: dlg.apply()
                Keys.onEnterPressed: dlg.apply()
            }
        }
        Label {
            objectName: "transposeProblem"
            visible: dlg.problem !== ""
            text: dlg.problem
            color: Theme.error; font: Theme.fontS
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }
    }
    footer: DialogFooter {
        Button { objectName: "transposeCancel"; text: "Cancel"; onClicked: dlg.close() }
        Button { objectName: "transposeOk"; text: "Transpose"; highlighted: true; onClicked: dlg.apply() }
    }
}
