import QtQuick
import QtQuick.Templates as T
import QtQuick.Controls.impl
import CNTheme

// A control's icon and text (replaces Controls' IconLabel): the icon is a
// PixelIcon, crisp at fractional scaling. Honours display and alignment.
// `display` is fine on a plain Item; on a Control or a Text, names such as
// display and right clash with FINAL properties (pitfall 2).
Item {
    id: root
    property url iconSource
    property color iconColor: Theme.icon
    property real iconSize: Theme.iconSize
    property string text
    property font font: Theme.font
    property color color: Theme.text
    property int display: T.AbstractButton.TextBesideIcon
    property real spacing: Theme.gap2
    property bool alignLeft: false
    readonly property bool hasIcon: String(iconSource) !== "" && display !== T.AbstractButton.TextOnly
    readonly property bool hasText: text !== "" && display !== T.AbstractButton.IconOnly
    implicitWidth: row.implicitWidth
    implicitHeight: Math.max(hasIcon ? ic.height : 0, hasText ? lbl.implicitHeight : 0)
    Row {
        id: row
        spacing: root.hasIcon && root.hasText ? root.spacing : 0
        x: root.alignLeft ? 0 : Math.round((root.width - width) / 2)
        anchors.verticalCenter: parent.verticalCenter
        PixelIcon {
            id: ic
            visible: root.hasIcon
            iconSource: root.iconSource
            color: root.iconColor
            size: root.iconSize
            anchors.verticalCenter: parent.verticalCenter
        }
        MnemonicLabel {
            id: lbl
            transform: SnapTranslate { target: lbl }
            visible: root.hasText
            text: root.text
            font: root.font
            color: root.color
            mnemonicVisible: false
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
