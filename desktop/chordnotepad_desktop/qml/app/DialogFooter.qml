import QtQuick
import QtQuick.Layouts
import CNTheme

// The one dialog button order: an optional destructive action alone on the
// left (`leading`), then the others, the primary (highlighted) last on the right.
RowLayout {
    id: footer
    default property alias buttons: trailing.data
    property alias leading: lead.data
    spacing: Theme.gap2
    Item { implicitWidth: Theme.gap6 - Theme.gap2; implicitHeight: Theme.controlHeight + Theme.gap6 }
    RowLayout { id: lead; spacing: Theme.gap2 }
    Item { Layout.fillWidth: true }
    RowLayout { id: trailing; spacing: Theme.gap2 }
    Item { implicitWidth: Theme.gap6 - Theme.gap2 }
}
