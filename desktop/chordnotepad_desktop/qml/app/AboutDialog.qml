pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// About Chord Notepad (plan step G2): Tk's content (main_window.py
// show_about) in the mockup's dialog style: the icon and name, the version
// and build lines (CI's build_info, or the dev-local values), the
// description, the copyright and licence. Open Source Licences opens on top
// of it (`licencesRequested`); Escape and Close close it.
AppDialog {
    id: dlg
    objectName: "aboutDialog"
    required property var dialogs
    readonly property var about: dlg.dialogs.about
    signal licencesRequested()

    title: "About Chord Notepad"
    width: Theme.px(130)
    closePolicy: Popup.CloseOnEscape
    contentItem: ColumnLayout {
        spacing: Theme.gap2
        Image {
            visible: dlg.about.icon !== ""
            source: dlg.about.icon
            sourceSize.width: Theme.px(24) * Theme.dpr
            sourceSize.height: Theme.px(24) * Theme.dpr
            width: Theme.px(24); height: Theme.px(24)
            Layout.preferredWidth: Theme.px(24); Layout.preferredHeight: Theme.px(24)
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.gap2
            smooth: true
            mipmap: true
        }
        Label {
            text: dlg.about.name
            font: Theme.fontHeadF
            Layout.alignment: Qt.AlignHCenter
        }
        GridLayout {
            objectName: "aboutBuild"
            columns: 2
            columnSpacing: Theme.gap2
            rowSpacing: Theme.px(0.5)
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.gap2
            Repeater {
                model: dlg.about.lines.length * 2
                delegate: Label {
                    required property int index
                    readonly property var line: dlg.about.lines[Math.floor(index / 2)]
                    text: index % 2 === 0 ? line.label : line.value
                    font: index % 2 === 0 ? Theme.fontStrongS : Theme.fontS
                    color: index % 2 === 0 ? Theme.text : Theme.muted
                    Layout.alignment: index % 2 === 0 ? Qt.AlignRight : Qt.AlignLeft
                }
            }
        }
        Label {
            text: dlg.about.description
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Layout.topMargin: Theme.gap3
        }
        Label {
            objectName: "aboutCopyright"
            text: dlg.about.copyright
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            color: Theme.muted
            font: Theme.fontC
            Layout.fillWidth: true
            Layout.topMargin: Theme.gap1
        }
    }
    footer: DialogFooter {
        Button { objectName: "aboutLicences"; text: "Open Source Licences"; onClicked: dlg.licencesRequested() }
        Button { objectName: "aboutClose"; text: "Close"; highlighted: true; onClicked: dlg.close() }
    }
}
