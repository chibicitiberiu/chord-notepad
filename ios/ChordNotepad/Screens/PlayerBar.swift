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

/// The player at the bottom in Play mode, laid out as Android's
/// `ui/play/Player.kt` and drawn as an iOS toolbar: the song pill (a pull-down
/// style button in the accent colour), then voicing · instrument · ⏮ · ▶/⏸ ·
/// metronome · speed · chord sheet as SF Symbols, then the status line. A
/// button that is on (the metronome, a speed other than 100 %, the chord
/// sheet) is tinted and filled. There's no Stop: ⏸ keeps the playhead, ⏮
/// stops and goes back to the start. `compact`: the narrow landscape column,
/// smaller buttons.
struct PlayerBar: View {
    let state: PlayerState
    let colors: AppColors
    var compact = false
    var actions: PlayerActions?
    /// A tap on the greyed voicing button says why (Android: a Toast).
    var explainLocked: (String) -> Void = { _ in }

    var body: some View {
        VStack(spacing: 0) {
            colors.separator.frame(height: 0.5).frame(height: 1, alignment: .top)
            VStack(spacing: 0) {
                songPill
                    .frame(height: 26)
                    .padding(.top, 2)
                buttons
                    .frame(height: 60)
                Text(state.status)
                    .font(.caption2)
                    .foregroundColor(colors.secondaryLabel)
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
        .background(colors.bar.ignoresSafeArea(edges: .bottom))
        // A fixed 110 pt bar: its text follows the text size up to a point.
        .dynamicTypeSize(...DynamicTypeSize.xxLarge)
    }

    /// ♩ 100 · 3/4 · Am ⌄ in the accent colour; opens Playback settings.
    private var songPill: some View {
        Button {
            actions?.songDefaults()
        } label: {
            HStack(spacing: 4) {
                Image(systemName: AppSymbols.songDefaults)
                    .font(.footnote)
                Text(state.pill)
                    .font(.footnote.weight(.medium))
                    .lineLimit(1)
                Image(systemName: AppSymbols.chevronDown)
                    .font(.caption2.weight(.semibold))
            }
            .padding(.horizontal, 8)
            .frame(maxHeight: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .accessibilityLabel(AccessibilityLabels.songDefaults(state.pill))
        .accessibilityIdentifier("player-pill")
    }

    private var buttons: some View {
        let side: CGFloat = compact ? 38 : 44
        return HStack(spacing: compact ? 0 : 4) {
            sideButton(AppSymbols.voicing, AccessibilityLabels.voicing(state.voicingLabel), on: false, size: side,
                       locked: state.voicingLockedReason, id: "player-voicing") { actions?.voicing() }
            sideButton(AppSymbols.instrument, AccessibilityLabels.instrument(state.instrumentLabel), on: false,
                       size: side, id: "player-instrument") { actions?.instrument() }
            sideButton(AppSymbols.rewind, AccessibilityLabels.rewind, on: false, size: side,
                       id: "player-rewind") { actions?.rewind() }
            playButton(size: compact ? 48 : 56)
            sideButton(state.metronome ? AppSymbols.metronomeOn : AppSymbols.metronome, AccessibilityLabels.metronome,
                       on: state.metronome, size: side, id: "player-metronome") { actions?.toggleMetronome() }
            sideButton(AppSymbols.speed, AccessibilityLabels.speed, on: state.speedBadge != nil, size: side,
                       badge: state.speedBadge, id: "player-speed") { actions?.speed() }
            sideButton(AppSymbols.chordSheet,
                       state.sheetVisible ? AccessibilityLabels.hideSheet : AccessibilityLabels.showSheet,
                       on: state.sheetVisible, size: side, id: "player-sheet") { actions?.toggleSheet() }
        }
        .frame(maxWidth: .infinity)
    }

    private func sideButton(_ symbol: String, _ label: String, on: Bool, size: CGFloat, badge: String? = nil,
                            locked: String? = nil, id: String, action: @escaping () -> Void) -> some View {
        Button {
            // A disabled button still takes a tap, to say why it's disabled.
            if let locked { explainLocked(locked) } else { action() }
        } label: {
            ZStack {
                Circle().fill(on ? colors.accent.opacity(0.15) : Color.clear)
                Image(systemName: symbol)
                    .font(.system(size: size < 40 ? 19 : 21))
                    .foregroundStyle(locked != nil ? colors.tertiaryLabel : on ? colors.accent : colors.label)
            }
            .frame(width: size, height: size)
            .overlay(alignment: .topTrailing) {
                if let badge {
                    Text(badge)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(colors.accent, in: Capsule())
                        .fixedSize()
                        .offset(x: 6, y: 0)
                }
            }
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityValue(locked ?? (on ? "on" : ""))
        .accessibilityIdentifier(id)
    }

    /// The big ▶/⏸ in the accent colour; a spinner over it while the song renders.
    private func playButton(size: CGFloat) -> some View {
        Button {
            actions?.playPause()
        } label: {
            ZStack {
                Circle().fill(colors.accent)
                Image(systemName: state.playing ? AppSymbols.pauseFill : AppSymbols.playFill)
                    .font(.system(size: size * 0.42))
                    .foregroundStyle(.white)
                    // ▶ sits a little right of the centre to look centred.
                    .offset(x: state.playing ? 0 : size * 0.04)
                    .opacity(state.starting ? 0 : 1)
                if state.starting {
                    ProgressView()
                        .tint(.white)
                }
            }
            .frame(width: size, height: size)
            .padding(.horizontal, size < 50 ? 2 : 4)
            .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(state.starting)
        .accessibilityLabel(state.playing ? AccessibilityLabels.pause : AccessibilityLabels.playSong)
        .accessibilityIdentifier("player-play")
    }
}
