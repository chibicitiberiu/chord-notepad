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

    /// Android's help screenshots' song (`android/tools/help_shot_songs/amazing_grace.txt`).
    static let grace = """
        {bpm: 90} {time: 3/4} {key: G}

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

        G             G7          C        G
        'Twas grace that taught my heart to fear
        G           Em        D
        And grace my fears relieved
        G             G7         C       G
        How precious did that grace appear
        G       Em      D        G
        The hour I first believed

        {loop: verse 2}

        // Ending
        C      G/B    Am7    D7sus4  G*6

        """

    /// What Android's `edit-keyboard` types into a new song.
    static let typed = "C  Am  F  G"
}
