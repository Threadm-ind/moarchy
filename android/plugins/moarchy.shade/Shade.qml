// Guest controls retain the mobile sheet and theme vocabulary. Android keeps
// Wi-Fi, Bluetooth, phone volume, screen brightness and device power controls.
import QtQuick
import QtQuick.Controls
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
  property var service: null
  property real progress: 0
  property bool dragging: false
  readonly property bool opened: progress >= 1 && !dragging
  readonly property string pluginId: "moarchy.shade"
  function open(payload): void { progress = 1 }
  function close(): void { progress = 0 }
  function toggle(payload): void { progress = opened ? 0 : 1 }
  Behavior on progress {
    enabled: !root.dragging
    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
  }
  function act(action): void {
    root.close()
    if (action === "themes") root.shell.summon("moarchy.themes", "{}")
    else if (action === "apps") root.shell.summon("moarchy.drawer", "{}")
    else if (action === "terminal") Quickshell.execDetached(["moarchy-launch-terminal"])
    else if (action === "keyboard") Quickshell.execDetached(["moarchy-toggle-keyboard"])
    else if (action === "exit") Quickshell.execDetached(["swaymsg", "exit"])
  }
  IpcHandler {
    target: "shade"
    function state(): string { return root.opened ? "open" : "closed" }
    function open(): string { root.open("{}"); return "ok" }
    function close(): string { root.close(); return "ok" }
    function metrics(): string {
      return JSON.stringify({ width: sheet.width, height: sheet.height,
        contentHeight: content.implicitHeight, viewportHeight: scroll.height,
        buttonHeight: 48, titleOverflow: heading.truncated })
    }
  }
  PanelWindow {
    id: edge
    anchors { top: true; left: true; right: true }
    implicitHeight: Math.max(32, Style.bar.sizeHorizontal)
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "moarchy-shade-edge"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    MouseArea {
      anchors.fill: parent
      property real startY: 0
      onPressed: mouse => { startY = mouse.y; root.dragging = true }
      onPositionChanged: mouse => {
        if (pressed) root.progress = Math.max(0, Math.min(1, (mouse.y - startY) / 180))
      }
      onReleased: {
        root.dragging = false
        root.progress = root.progress > 0.25 ? 1 : 0
      }
      onClicked: root.progress = 1
      onCanceled: { root.dragging = false; root.progress = 0 }
    }
  }
  PanelWindow {
    id: sheet
    visible: root.progress > 0
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "moarchy-shade"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    Rectangle {
      anchors.fill: parent
      color: Color.bar.background
      opacity: 0.96 * root.progress
    }
    ScrollView {
      id: scroll
      anchors { fill: parent; margins: 20; topMargin: Math.max(48, Style.bar.sizeHorizontal + 12) }
      opacity: root.progress
      clip: true
      contentWidth: availableWidth
      Column {
        id: content
        width: scroll.availableWidth
        spacing: 12
        Text {
          id: heading
          width: parent.width
          text: "Desktop"
          color: Color.bar.text
          font { family: Style.font.family; pixelSize: 24; weight: Font.DemiBold }
          elide: Text.ElideRight
        }
        Text {
          width: parent.width
          text: "Phone controls stay in Android’s notification panel."
          color: Color.bar.text
          font { family: Style.font.family; pixelSize: 14 }
          wrapMode: Text.WordWrap
          bottomPadding: 12
        }
        Repeater {
          model: [
            { label: "Apps", action: "apps" },
            { label: "Terminal", action: "terminal" },
            { label: "Themes", action: "themes" },
            { label: "Keyboard", action: "keyboard" },
            { label: "Close desktop", action: "exit" },
            { label: "Back", action: "back" }
          ]
          delegate: Button {
            id: button
            required property var modelData
            width: content.width
            height: 48
            text: modelData.label
            Accessible.name: text
            onClicked: root.act(modelData.action)
            background: Rectangle {
              radius: 12
              color: button.down ? Color.bar.active : "transparent"
              border { width: button.activeFocus ? 2 : 1; color: Color.bar.text }
            }
            contentItem: Text {
              text: button.text
              font { family: Style.font.family; pixelSize: 15; weight: Font.DemiBold }
              color: Color.bar.text
              horizontalAlignment: Text.AlignHCenter
              verticalAlignment: Text.AlignVCenter
              elide: Text.ElideRight
            }
          }
        }
      }
    }
  }
}
