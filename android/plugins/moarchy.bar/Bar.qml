// Android owns phone hardware status. This bar reports the guest and its clock.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

Item {
  id: root
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var barWidgetRegistry: null
  property var pluginRegistry: null
  property var barConfig: ({})
  readonly property int barSize: Math.max(32, Style.bar.sizeHorizontal)
  readonly property bool barHidden: false
  readonly property string position: "top"
  readonly property string fontFamily: Style.font.family
  function summonBarWidget(id: string): bool { return false }
  function hideBarWidget(id: string): bool { return false }
  function isBarWidgetOpen(id: string): bool { return false }
  function panelWidgetIdAt(section: string, index: string): string { return "" }
  function debugBarGeometry(): var { return [] }
  SystemClock { id: clock; precision: SystemClock.Minutes }
  IpcHandler {
    target: "bar"
    function metrics(): string {
      return JSON.stringify({ height: root.barSize, font: root.fontFamily, hostStatus: false })
    }
  }
  Variants {
    model: Quickshell.screens
    delegate: Component {
      PanelWindow {
        required property var modelData
        screen: modelData
        anchors { top: true; left: true; right: true }
        implicitHeight: root.barSize
        color: Color.bar.background
        WlrLayershell.namespace: "moarchy-bar"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        exclusionMode: ExclusionMode.Auto
        Text {
          anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
          text: Qt.formatDateTime(clock.date, "H:mm")
          font { family: root.fontFamily; pixelSize: Style.font.body; weight: Font.DemiBold }
          color: Color.bar.text
        }
        Text {
          anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
          text: "Moarchy"
          font { family: root.fontFamily; pixelSize: Style.font.body; weight: Font.DemiBold }
          color: Color.bar.text
        }
      }
    }
  }
}
