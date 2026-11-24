import ChordNotepadKit
import SwiftUI

/// What the player's buttons do; nil in the catalog (inert).
struct PlayerActions {
    var songDefaults: () -> Void
    var voicing: () -> Void
    var instrument: () -> Void
    var rewind: () -> Void
    var playPause: () -> Void
    var toggleMetronome: () -> Void
    var speed: () -> Void
    var toggleSheet: () -> Void
}

/// The player at the bottom in Play mode (Android's `ui/play/Player.kt`): the
/// song pill, then voicing · instrument · ⏮ · ▶/⏸ · metronome · speed · chord
/// sheet, then the status line. The side icons are monochrome, softly tinted
/// when on. There's no Stop: ⏸ keeps the playhead, ⏮ stops and goes back to
/// the start. `compact`: the narrow landscape column, smaller buttons.
struct PlayerBar: View {
    let state: PlayerState
    let colors: AppColors
    var compact = false
    var actions: PlayerActions?
    /// A tap on the greyed voicing button says why (Android: a Toast).
    var explainLocked: (String) -> Void = { _ in }

    var body: some View {
        VStack(spacing: 0) {
            colors.line.swiftUI.frame(height: 1)
            VStack(spacing: 0) {
                songPill
                    .frame(height: 26)
                    .padding(.top, 2)
                buttons
                    .frame(height: 60)
                Text(state.status)
                    .font(.caption2)
                    .foregroundColor(colors.muted.swiftUI)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(maxWidth: .infinity)
                    .frame(height: 16)
                    .accessibilityIdentifier("player-status")
            }
            .padding(.horizontal, 10)
            .padding(.top, 2)
            .padding(.bottom, 3)
        }
        .frame(height: MainMetrics.playerHeight)
        .background(colors.surface2.swiftUI)
        // A fixed 110 pt bar: its text follows the text size up to a point.
        .dynamicTypeSize(...DynamicTypeSize.xxLarge)
    }

    /// 𝄞 100 · 3/4 · Am ⌄: muted purple text, no background; opens the song defaults.
    private var songPill: some View {
        Button {
            actions?.songDefaults()
        } label: {
            HStack(spacing: 4) {
                MdiIcon("mdi_music_clef_treble", tint: colors.pill.swiftUI, size: 15)
                Text(state.pill)
                    .font(.footnote.weight(.medium))
                    .foregroundColor(colors.pill.swiftUI)
                    .lineLimit(1)
                MdiIcon("mdi_chevron_down", tint: AppColors.offTint.swiftUI, size: 15)
            }
            .padding(.horizontal, 8)
            .frame(maxHeight: .infinity)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Playback settings: \(state.pill)")
        .accessibilityIdentifier("player-pill")
    }

    private var buttons: some View {
        let side: CGFloat = compact ? 38 : 42
        return HStack(spacing: compact ? 0 : 6) {
            sideButton("mdi_music", "Voicing: \(state.voicingLabel)", on: false, size: side,
                       locked: state.voicingLockedReason, id: "player-voicing") { actions?.voicing() }
            sideButton("mdi_guitar_acoustic", "Instrument: \(state.instrumentLabel)", on: false, size: side,
                       id: "player-instrument") { actions?.instrument() }
            sideButton("mdi_skip_previous", "Back to the start (stops playback)", on: false, size: side,
                       id: "player-rewind") { actions?.rewind() }
            playButton(size: compact ? 48 : 54)
            sideButton("mdi_metronome", "Metronome", on: state.metronome, size: side,
                       id: "player-metronome") { actions?.toggleMetronome() }
            sideButton("mdi_speedometer", "Speed", on: state.speedBadge != nil, size: side, badge: state.speedBadge,
                       id: "player-speed") { actions?.speed() }
            sideButton("mdi_dock_bottom", state.sheetVisible ? "Hide the chord sheet" : "Show the chord sheet",
                       on: state.sheetVisible, size: side, id: "player-sheet") { actions?.toggleSheet() }
        }
        .frame(maxWidth: .infinity)
    }

    private func sideButton(_ icon: String, _ label: String, on: Bool, size: CGFloat, badge: String? = nil,
                            locked: String? = nil, id: String, action: @escaping () -> Void) -> some View {
        let tint = (on ? colors.primary : colors.icon).withAlpha(locked == nil ? 1 : AppColors.disabledAlpha)
        return Button {
            // A disabled button still takes a tap, to say why it's disabled.
            if let locked { explainLocked(locked) } else { action() }
        } label: {
            ZStack {
                Circle().fill(on ? colors.primarySoft.swiftUI : Color.clear)
                MdiIcon(icon, tint: tint.swiftUI, size: size < 40 ? 24 : 26)
            }
            .frame(width: size, height: size)
            .overlay(alignment: .topTrailing) {
                if let badge {
                    Text(badge)
                        .font(.system(size: 9, weight: .medium))
                        .foregroundColor(colors.onPrimary.swiftUI)
                        .padding(.horizontal, 3)
                        .padding(.vertical, 1)
                        .background(colors.primary.swiftUI, in: RoundedRectangle(cornerRadius: 6))
                        .fixedSize()
                        .offset(x: 4, y: 2)
                }
            }
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityValue(locked ?? (on ? "on" : ""))
        .accessibilityIdentifier(id)
    }

    /// The big round ▶/⏸ in the primary colour; a ring while the song renders.
    private func playButton(size: CGFloat) -> some View {
        Button {
            actions?.playPause()
        } label: {
            ZStack {
                Circle()
                    .fill(colors.primary.swiftUI)
                    .shadow(color: .black.opacity(0.25), radius: 2, y: 1)
                MdiIcon(state.playing ? "mdi_pause" : "mdi_play", tint: colors.onPrimary.swiftUI, size: 34)
                if state.starting {
                    Circle()
                        .trim(from: 0, to: 0.7)
                        .stroke(colors.onPrimary.swiftUI, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                        .padding(4.5)
                }
            }
            .frame(width: size, height: size)
            .padding(.horizontal, size < 50 ? 2 : 4)
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(state.starting)
        .accessibilityLabel(state.playing ? "Pause" : "Play")
        .accessibilityIdentifier("player-play")
    }
}
