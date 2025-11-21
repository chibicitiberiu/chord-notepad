# Chord Notation Systems and Detection Guide

## Overview of Chord Notation Systems

### American Notation (Alphabetic)
The American system uses the first seven letters of the alphabet: **C, D, E, F, G, A, B**

**Structure:** `[Root Note][Accidental][Quality][Extensions]`

- **Root Notes:** C, D, E, F, G, A, B
- **Accidentals:** # (sharp) or b (flat)
- **Quality Modifiers:** m (minor), maj, dim, aug, sus, add
- **Extensions:** 7, 9, 11, 13, 6, 4, 2

**Examples:**
- C = C major
- Cm = C minor
- C7 = C dominant seventh
- Cmaj7 = C major seventh
- Cm7b5 = C minor seventh flat five (half-diminished)
- Csus4 = C suspended fourth
- Cadd9 = C major add nine
- C#m7 = C sharp minor seventh

### European Notation (Solfege)
The European system uses solfege syllables: **Do, Re, Mi, Fa, Sol, La, Si** (or Ti in some regions)

**Structure:** `[Root Note][Accidental][Quality][Extensions]`

- **Root Notes:** Do, Re, Mi, Fa, Sol, La, Si
- **Accidentals:** # (sharp) or b (flat), or ♯, ♭ (musical symbols)
- **Quality Modifiers:** m (minor), maj, dim, aug, sus, add
- **Extensions:** 7, 9, 11, 13, 6, 4, 2

**Examples:**
- Do = Do major
- Dom = Do minor
- Do7 = Do dominant seventh
- Domaj7 = Do major seventh
- Dom7b5 = Do minor seventh flat five
- Dosus4 = Do suspended fourth
- Doadd9 = Do major add nine
- Do#m7 = Do sharp minor seventh

### Comparison Table

| American | European | Meaning |
|----------|----------|---------|
| C | Do | C major |
| Cm | Dom | C minor |
| C# | Do# | C sharp |
| Cb | Dob | C flat |
| C7 | Do7 | Dominant 7th |
| Cmaj7 | Domaj7 | Major 7th |
| Cm7 | Dom7 | Minor 7th |
| Cdim | Dodim | Diminished |
| Caug | Doaug | Augmented |

## Chord Types and Common Patterns

### 1. Triad Chords (Basic)
- **Major:** C, D, E, F, G, A, B
- **Minor:** Cm, Dm, Em, Fm, Gm, Am, Bm (or with 'm' suffix)
- **Diminished:** Cdim, Ddim, Edim (or C°, D°)
- **Augmented:** Caug, Daug, Eaug (or C+, D+)

### 2. Seventh Chords
- **Dominant 7th:** C7, D7, E7 (major triad + minor 7th)
- **Major 7th:** Cmaj7, Dmaj7, Emaj7 (major triad + major 7th)
- **Minor 7th:** Cm7, Dm7, Em7 (minor triad + minor 7th)
- **Half-Diminished:** Cm7b5, Dm7b5 (diminished triad + minor 7th)
- **Diminished 7th:** Cdim7, Ddim7 (diminished triad + diminished 7th)
- **Minor-Major 7th:** Cm(maj7), Dm(maj7)

### 3. Suspended Chords
- **Sus2:** Csus2, Dsus2 (replaces 3rd with 2nd)
- **Sus4:** Csus4, Dsus4 (replaces 3rd with 4th)
- **Sus2-Sus4:** Csus2sus4, Dsus2sus4

### 4. Added Note Chords
- **Add9:** Cadd9, Dadd9 (major chord + 9th)
- **Add11:** Cadd11, Dadd11
- **Add4:** Cadd4, Dadd4
- **Add6:** Cadd6, Dadd6 (also called "6th chord")

### 5. Extended Chords
- **9th:** C9, D9 (dominant 7 + 9th)
- **Major 9th:** Cmaj9, Dmaj9
- **Minor 9th:** Cm9, Dm9
- **11th:** C11, D11
- **13th:** C13, D13
- **Alterations:** C7b9, C7#11, C7alt

### 6. Complex/Jazz Chords
- **Polychords:** C/G, D/A (bass note separated by slash)
- **Slash chords:** Dm/F, Am/G
- **Extended alterations:** Cmaj7#11, Cm7b5b9, C7#5b9

## Regex Pattern Development

### Challenge: Distinguishing Chords from Words
Chords have specific characteristics that separate them from regular text:

1. **Single letter or double letter root** (C, D, E, F, G, A, B, Do, Re, Mi, Fa, Sol, La, Si)
2. **Optional accidentals** (# or b immediately after root)
3. **Chord quality markers** appear in specific patterns:
   - m, maj, min, minor (case-insensitive in some contexts)
   - dim, aug, sus (quality modifiers)
   - 7, 9, 11, 13, 6, 4, 2 (extensions/alterations)
4. **Case sensitivity:** Usually capital first letter (C, not c)
5. **Context:** Chords appear in musical contexts

### Words That Look Like Chords (False Positives)
- "A" (article)
- "B" (letter)
- "E" (letter)
- "I" (pronoun)
- "an" (article)
- "am" (verb)
- "add" (verb)
- "dim" (adjective)
- "do" (verb, European notation)

## Comprehensive Regex Patterns

### Pattern 1: American Notation (Strict)
Matches chords with capital letter roots, optional accidentals, and quality markers.

```regex
\b([A-G][#b]?)(m|min|minor)?(?:(maj|maj7|7|9|11|13|6|4|2|sus2|sus4|sus|dim|aug|add\d?)+(b\d+|#\d+)*)?\b
```

**Breakdown:**
- `\b` - Word boundary
- `([A-G][#b]?)` - Root note: single letter A-G, optionally followed by # or b
- `(m|min|minor)?` - Optional minor indicator
- `(?:...)` - Non-capturing group for remaining elements
- `(maj|maj7|7|9|11|13|6|4|2|sus2|sus4|sus|dim|aug|add\d?)+` - Quality and extension markers
- `(b\d+|#\d+)*` - Optional alterations (flat or sharp with interval number)
- `\b` - Word boundary

**Examples matched:**
- C, Cm, C7, Cmaj7, Cm7b5, Csus4, Cadd9, C#7, Cbmaj7

**Examples NOT matched:**
- "add" (standalone word)
- "am" (verb without a number or quality)
- "a" (article)

---

### Pattern 2: American Notation (Comprehensive - Allow Variations)
More lenient pattern accounting for different spacing and notation styles.

```regex
\b([A-G][#b]?(?:m|min|minor)?(?:(?:maj|maj7)?(?:\d+)?(?:b\d+|#\d+)?|(?:7|9|11|13|6|4|2)?(?:b\d+|#\d+)?|dim|aug|add\d+|sus[24]?)*)\b(?=[^a-z]|$)
```

This is complex because it tries to match many valid variations. A better approach is Pattern 3.

---

### Pattern 3: American Notation (Most Practical - Recommended)
Balance between being comprehensive and avoiding false positives.

```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|sus|dim|aug|add[4-9])?(?:[b#]\d+)*)\b
```

**Breakdown:**
- `\b([A-G](?:[#b])?)` - Root: A-G with optional accidental
- `(?:...)` - Non-capturing group for quality
- `(?:m(?:aj)?(?:7|9|11|13)?` - m, maj, or m + extension
- `|min|maj7|maj9|maj11|maj13` - Alternative quality formats
- `|7|9|11|13|6|sus[24]|sus|dim|aug|add[4-9])` - Other qualities
- `(?:[b#]\d+)*` - Optional alterations
- `\b` - Word boundary

**Examples matched:**
- C, Cm, Cmaj7, C7, C9, Csus4, Cadd9, C#m7, Cbmaj7, C7b5

---

### Pattern 4: European Notation (Solfege)
Matches Do, Re, Mi, Fa, Sol, La, Si with modifiers.

```regex
\b(Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|sus|dim|aug|add[4-9])?(?:[b#]\d+)*\b
```

**Breakdown:**
- `\b(Do|Re|Mi|Fa|Sol|La|Si)` - Root note in solfege
- Rest is identical to American notation pattern

**Examples matched:**
- Do, Dom, Domaj7, Do7, Do9, Dosus4, Doadd9, Do#m7

**Note:** Be careful with "Do" - it's also a common English word. Context matters.

---

### Pattern 5: Combined American + European (Full Coverage)
Single pattern matching both notations.

```regex
\b(?:([A-G]|Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|sus|dim|aug|add[4-9])?(?:[b#]\d+)*)\b
```

---

### Pattern 6: With Bass Note (Slash Chords)
Matches chords with explicit bass notes (e.g., C/G, Dm/F).

```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj\d?|7|9|11|13|6|sus[24]|dim|aug|add[4-9])?(?:[b#]\d+)*)\s*/\s*([A-G](?:[#b])?)\b
```

**Examples matched:**
- C/G, Dm/F, Gmaj7/B, Am7/E

---

### Pattern 7: Negative Lookahead (Avoid False Positives)
Use negative lookahead to exclude common words.

```regex
\b(?!and\b|are\b|add\b|am\b)([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add[4-9])?(?:[b#]\d+)*)\b
```

This prevents matching "am", "are", "and", while allowing "add9" as part of a chord.

---

### Pattern 8: Case-Insensitive for Flexible Input
Matches both uppercase and lowercase roots.

```regex
(?i)\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj[79]|7|9|11|13|6|sus[24]|dim|aug|add[4-9])?(?:[b#]\d+)*)\b
```

Adding `(?i)` flag enables case-insensitive matching.

---

## Implementation Recommendations

### 1. For Basic Music Applications
Use **Pattern 3** or **Pattern 7** (American notation with negative lookahead).
- Fast and reliable
- Covers 95% of common chord notations
- Minimal false positives

### 2. For International Support
Use **Pattern 5** (Combined American + European).
- Handles both notations
- Slightly more complex but comprehensive

### 3. For Advanced Music Analysis
Combine **Pattern 6** (slash chords) with additional validation:
- Check that the root note is valid
- Verify quality markers appear in correct order
- Cross-reference against known chord dictionaries

### 4. For Strict Validation
Use **Pattern 7** with negative lookahead:
```regex
\b(?!and\b|are\b|am\b|add(?!\d))([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

## Testing Examples

### Should Match (True Positives)
- C, D, E, F, G, A, B (major triads)
- Cm, Dm, Em, Fm, Gm, Am, Bm (minor triads)
- C7, D7, E7 (dominant sevenths)
- Cmaj7, Dmaj7, Emaj7 (major sevenths)
- Cm7, Dm7, Em7 (minor sevenths)
- Csus4, Dsus2, Esus4 (suspended)
- Cadd9, Dadd11, Eadd4 (added notes)
- C#, Db, E#, Fb (enharmonic equivalents)
- Cm7b5, D7#9, E7alt (altered chords)
- Do, Domaj7, Dosus4 (European notation)

### Should NOT Match (True Negatives)
- "am" (verb alone)
- "A" at start of sentence (article)
- "add" standalone (verb)
- "dim" standalone (adjective)
- "do" standalone (verb - but "Do" at phrase start might match)
- "music" (contains letters but not a chord)
- "B-side" (letter followed by hyphen)
- "B.B. King" (isolated letters)

### May Match (Context-Dependent)
- "I" - could be article or chord (depends on music context)
- "A" - could be article or chord
- "B" - could be letter or chord (British notation for B-flat)
- "Do" - could be verb or Do major (European notation)

## Advanced Detection Strategies

### Strategy 1: Context-Based Detection
Analyze surrounding words:
- Keywords that suggest musical context: "play", "chord", "guitar", "piano", "key", "progression"
- Keywords that suggest non-musical context: "article", "word", "letter", "sentence"

### Strategy 2: Whitelist Validation
Maintain a list of all valid chord roots and qualities:
```
Roots: A, B, C, D, E, F, G, Do, Re, Mi, Fa, Sol, La, Si
Qualities: m, maj, 7, 9, 11, 13, 6, sus, dim, aug, add
```

Validate detected chords against this list.

### Strategy 3: Position-Based Detection
- Chords often appear in lists or progressions (e.g., "C - F - G")
- Chords appear within brackets or after labels (e.g., "[C]", "Verse: C F G")
- Use this contextual information to increase confidence

### Strategy 4: Machine Learning (Advanced)
Train a classifier on labeled chord/non-chord examples to handle edge cases and context.

## Common Pitfalls and Solutions

| Problem | Solution |
|---------|----------|
| Matching "am", "an", "a" | Use negative lookahead: `(?!am\b)`, check for quality marker after root |
| Matching "B" as chord in "B-side" | Require word boundary after: `B\b` instead of `B` |
| Matching "Do" as English verb | Require music context or capital letter in non-solfege |
| Matching "add" standalone | Require digit after "add": `add\d` instead of `add` |
| European notation false positives | Restrict to "Do", "Re", "Mi" etc., not "do", "re", "mi" |
| Slash chord confusion | Separate parsing: find chord, then check for `/note` |

## Regex Testing Online Tools

For testing and refining these patterns, use:
- https://regex101.com/ (supports PCRE, JavaScript, Python)
- https://regexper.com/ (visualizes regex patterns)
- https://www.regexpal.com/ (quick testing)

## Language-Specific Examples

### JavaScript
```javascript
const chordPattern = /\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;
const text = "Play C major, then F, and finish with G7.";
const matches = text.match(chordPattern);
// matches: ["C", "F", "G7"]
```

### Python
```python
import re
chord_pattern = r'\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
text = "Play C major, then F, and finish with G7."
matches = re.findall(chord_pattern, text)
# matches: ['C', 'F', 'G7']
```

### PHP
```php
$pattern = '/\b([A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/';
$text = "Play C major, then F, and finish with G7.";
preg_match_all($pattern, $text, $matches);
// $matches[1]: array('C', 'F', 'G7')
```

---

## Summary

**Best General-Purpose Pattern (Recommended):**
```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

**With False Positive Protection:**
```regex
\b(?!am\b|are\b|and\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

**For European Notation:**
```regex
\b((?:Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

These patterns handle the vast majority of musical chord notations while minimizing false positives in regular text.
