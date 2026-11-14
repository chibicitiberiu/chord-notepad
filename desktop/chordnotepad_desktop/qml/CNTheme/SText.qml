import QtQuick

// Text whose origin is snapped to whole device pixels (see SnapTranslate).
Text {
    id: t
    transform: SnapTranslate { target: t }
}
