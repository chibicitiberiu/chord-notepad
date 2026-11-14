import QtQuick
import CNTheme

PixelIcon {
    property string direction: "down"   // down | right | up
    name: "chevron-" + direction
    size: Theme.iconSmall
    color: Theme.muted
}
