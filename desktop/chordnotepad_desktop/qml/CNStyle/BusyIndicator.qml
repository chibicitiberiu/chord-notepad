pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Templates as T
import CNTheme

// A small spinner in the accent colour: eight dots fading round a circle,
// turning while `running` (Suggest Capo while it scores). Hidden when not
// running, so a stopped one takes its space but shows nothing.
T.BusyIndicator {
    id: control
    implicitWidth: Theme.px(6)
    implicitHeight: Theme.px(6)
    contentItem: Item {
        implicitWidth: Theme.px(6)
        implicitHeight: Theme.px(6)
        visible: control.running
        Item {
            id: ring
            anchors.fill: parent
            Repeater {
                model: 8
                Rectangle {
                    id: dot
                    required property int index
                    readonly property real reach: (ring.width - dot.width) / 2
                    width: ring.width * 0.2; height: dot.width; radius: dot.width / 2
                    color: Theme.accent
                    opacity: 0.2 + 0.8 * dot.index / 7
                    x: dot.reach + dot.reach * Math.cos(dot.index * Math.PI / 4)
                    y: dot.reach + dot.reach * Math.sin(dot.index * Math.PI / 4)
                }
            }
            RotationAnimator on rotation {
                from: 0; to: 360; duration: 1000
                loops: Animation.Infinite
                running: control.running && control.visible
            }
        }
    }
}
