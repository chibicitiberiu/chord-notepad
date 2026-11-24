import Foundation

/// The texts CI's live help screenshots use (`-CNScreen hint`, `keyboard`),
/// as Android's help shot scenes have them (`android/tools/help_shots.json`).
enum HelpShotSongs {
    /// Android's `typo_play`: Amazing Grace's first verse under a tempo out of range.
    static let typo = """
        {bpm: 500} {time: 3/4} {key: G}

        // Amazing Grace (John Newton, 1779)
        {label: verse}
        G           G7        C      G
        Amazing grace, how sweet the sound
        G               Em      D
        That saved a wretch like me
        G            G7       C      G
        I once was lost, but now am found
        G      Em       D       G
        Was blind, but now I see

        """

    /// What Android's `edit-keyboard` types into a new song.
    static let typed = "C  Am  F  G"
}
