# Chord Regex Pattern - Visual Guide and Breakdown

This document provides visual explanations of how chord detection regex patterns work.

## Master Pattern (Recommended)

```regex
\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

### Visual Breakdown

```
\b                                    Word boundary (start)
  (?!am\b|are\b|and\b|add\b)        Negative lookahead: exclude these words
    (                                 Capture group starts
      [A-G]                           Root note: A through G
      (?:[#b])?                       Optional accidental: sharp or flat
      (?:                             Non-capturing group for quality
        m(?:aj)?                      m or maj (minor or major)
        (?:7|9|11|13)?                Optional: 7, 9, 11, or 13
        |                             OR
        min|maj7|maj9|               Alternative quality spellings
        maj11|maj13|7|9|11|13|6|     Numeric qualities
        sus[24]|                      Suspended 2 or 4
        dim|aug|                      Diminished or augmented
        add\d                         Add followed by digit
      )?                              Quality is optional
      (?:[b#]\d+)*                   Optional alterations: flat/sharp + number
    )                                 Capture group ends
\b                                    Word boundary (end)
```

## Pattern Component Functions

### 1. Word Boundaries: `\b`

```
Input: "Play C major"
              ^
        Word boundary here

\b matches the position before 'C'
```

Ensures we don't match partial words:
- ✓ Matches: "C" in "Play **C** major"
- ✗ Rejects: "C" in "**C**amel" (part of word)

### 2. Negative Lookahead: `(?!am\b|are\b|and\b|add\b)`

```
Input: "I am ready, and you are too"
       ^  ^^        ^^^     ^^^

(?!am\b)   - Prevents matching "am"
(?!are\b)  - Prevents matching "are"
(?!and\b)  - Prevents matching "and"
(?!add\b)  - Prevents matching "add" (without digit)
```

How it works:
1. Checks if next characters match any excluded pattern
2. If yes, skips this position
3. If no, continues with the rest of the pattern

Examples:
- ✗ "am" - Rejected by lookahead
- ✗ "Are you ready" - "Are" rejected
- ✓ "Am7" - Passes lookahead (followed by "7")
- ✓ "Cadd9" - Passes lookahead (followed by "9")

### 3. Root Note: `[A-G]`

```
Character class matching single letter A through G

[A-G] matches:
  A, B, C, D, E, F, G

Examples:
  ✓ C     (matches C)
  ✓ G     (matches G)
  ✗ H     (not in range)
  ✗ z     (not in range)
```

### 4. Accidental (Sharp/Flat): `(?:[#b])?`

```
(?:           - Non-capturing group
  [#b]        - Character class: # or b
)?            - Optional (0 or 1 times)

Examples:
  C      →  No accidental (optional, so ok)
  C#     →  Sharp (matches #)
  Cb     →  Flat (matches b)
  C##    →  First # matches, second doesn't (pattern expects quality after)
```

### 5. Quality Markers

#### Pattern Branch 1: m and variations
```
m(?:aj)?(?:7|9|11|13)?

Breaks down as:
  m           - Literal 'm'
  (?:aj)?     - Optional 'aj' (making 'maj')
  (?:7|9...?) - Optional number

Matches:
  ✓ m        (minor)
  ✓ maj      (major)
  ✓ m7       (minor seventh)
  ✓ maj7     (major seventh)
  ✓ maj9     (major ninth)
  ✗ maj      (not matched - needs quality after)
```

#### Pattern Branch 2: Alternative spellings
```
min|maj7|maj9|maj11|maj13|7|9|11|13|6

Direct matches:
  ✓ min      (alternative minor)
  ✓ maj7     (alternative major 7)
  ✓ 7        (dominant 7)
  ✓ 9, 11, 13 (extended chords)
  ✓ 6        (sixth chord)
```

#### Pattern Branch 3: Special qualities
```
sus[24]|dim|aug|add\d

Matches:
  ✓ sus2, sus4  (suspended)
  ✓ dim         (diminished)
  ✓ aug         (augmented)
  ✓ add9        (add digit required)
```

### 6. Alterations: `(?:[b#]\d+)*`

```
(?:           - Non-capturing group
  [b#]        - Flat or sharp
  \d+         - One or more digits
)*            - Zero or more times (can repeat)

Examples:
  C7b5      →  [7] then [b5]
  C7#11     →  [7] then [#11]
  C7b9#11   →  [7] then [b9] then [#11]
  Cm7b5     →  [m7] then [b5]
```

## Complete Example Walkthrough

### Example 1: "Dm7b5"

```
Text: "Dm7b5"
      D  m  7  b  5

Step 1: \b
        ↓
        Position before 'D' - word boundary found ✓

Step 2: (?!am\b|are\b|and\b|add\b)
        Lookahead checks: is this "am"? no, "are"? no, "and"? no ✓

Step 3: [A-G]
        D matches letter A-G ✓

Step 4: (?:[#b])?
        Next char is 'm', not # or b - optional, so ✓

Step 5: (?:m(?:aj)?(?:7|9|11|13)?...)
        'm' matches first branch 'm(?:aj)?(?:7|9|11|13)?'
        Next is '7', which matches (?:7|9|11|13)? ✓

Step 6: (?:[b#]\d+)*
        'b5' matches [b#]\d+ ✓
        End of string, no more matches needed ✓

Step 7: \b
        End of string - word boundary ✓

Result: ✓ MATCH - "Dm7b5"
```

### Example 2: "am playing"

```
Text: "am playing"
      am

Step 1: \b
        Position before 'a' - word boundary ✓

Step 2: (?!am\b|are\b|and\b|add\b)
        Lookahead checks: is this "am"? YES! ✗

        Pattern fails here, does not match

Result: ✗ NO MATCH - "am" correctly excluded
```

### Example 3: "Am7 chord"

```
Text: "Am7 chord"
      Am7

Step 1: \b
        Position before 'A' - word boundary ✓

Step 2: (?!am\b|are\b|and\b|add\b)
        Lookahead checks: is this "am"? NO (followed by '7', not word boundary) ✓

Step 3: [A-G]
        'A' matches ✓

Step 4: (?:[#b])?
        Next char is 'm', not # or b - optional ✓

Step 5: (?:m(?:aj)?(?:7|9|11|13)?...)
        'm' matches, '7' matches ✓

Step 6: (?:[b#]\d+)*
        Next char is space, no alterations ✓

Step 7: \b
        Space is word boundary ✓

Result: ✓ MATCH - "Am7"
```

## Pattern Alternatives

### When C# by itself is OK

If you need to match bare accidentals like "C#" without quality:

```regex
\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:(?:m|maj|min|7|9|11|13|6|sus|dim|aug|add\d)(?:[b#]\d+)*)?)\b
```

The change: Make quality fully optional with nested `(?:...)?`

### Simpler (Without False Positive Protection)

If you don't need to exclude "am", "are", "and":

```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b
```

Just remove the `(?!am\b|are\b|and\b|add\b)` part.

## Performance Considerations

### Backtracking

The pattern is designed to minimize backtracking:

```regex
[A-G]           ← Single character match (no backtracking)
(?:[#b])?       ← Optional, single char (minimal backtracking)
(?:...)?        ← Quality is optional but specific (no excessive backtracking)
(?:[b#]\d+)*    ← Limited to digit count (no long backtracking)
```

### Lookahead Performance

Negative lookahead `(?!...)` has minimal performance impact because:
- It only checks ahead, doesn't consume characters
- It's at the start before expensive matching
- Limited alternatives (4 words)

## Testing Your Pattern

### Using Regex101.com

1. Go to https://regex101.com/
2. Paste pattern in "Regular Expression" field
3. Paste test text in "Test String" field
4. Use "g" flag for global (multiple matches)
5. Observe matches highlighted in blue

### Using Node.js

```javascript
const pattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;

const text = "Play C major, Dm7, and G7";
const matches = text.match(pattern);
console.log(matches); // ['C', 'Dm7', 'G7']
```

### Using Python

```python
import re

pattern = r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'

text = "Play C major, Dm7, and G7"
matches = re.findall(pattern, text)
print(matches)  # ['C', 'Dm7', 'G7']
```

## Common Mistakes

### Mistake 1: Wrong Character Class

```regex
[A-G]    ✓ Correct - matches single char in range
[A]-[G]  ✗ Wrong - matches literal dash between A and G
```

### Mistake 2: Forgetting Escape

```regex
\d       ✓ Correct - matches any digit
d        ✗ Wrong - matches literal 'd'
```

### Mistake 3: Mixing Capturing and Non-Capturing

```regex
([A-G])          ✓ Capturing - gets returned
(?:[A-G])        ✓ Non-capturing - ignored
([A-G])?         ✓ Optional capture
(?:[A-G])?       ✓ Optional non-capture
```

### Mistake 4: Forgetting Word Boundaries

```regex
\b[A-G]\b        ✓ Only matches isolated letters
[A-G]            ✗ Matches C in "Camel"
```

## Summary

The recommended pattern is structured as:

1. **Anchor** (`\b`) - Ensure position is valid
2. **Guard** (`(?!...)`) - Exclude false positives
3. **Capture** (`(...)`) - Get the chord
4. **Root** (`[A-G]`) - Letter A-G
5. **Accidental** (`[#b]?`) - Optional sharp/flat
6. **Quality** (`m|maj|7|...`) - Type of chord
7. **Alterations** (`[b#]\d+*`) - Modifications
8. **Anchor** (`\b`) - Ensure end is valid

This structure balances:
- Correctness (catches real chords)
- Precision (avoids false positives)
- Performance (minimal backtracking)
- Readability (logical grouping)

---

## Reference: All Character Classes

| Class | Means | Examples |
|-------|-------|----------|
| `.` | Any character | `a`, `1`, `@` |
| `[abc]` | Any of these | `a`, `b`, `c` |
| `[a-z]` | Range | `a` through `z` |
| `[^abc]` | NOT these | anything except `a`, `b`, `c` |
| `\d` | Digit | `0-9` |
| `\D` | Non-digit | anything except `0-9` |
| `\w` | Word char | `a-z`, `A-Z`, `0-9`, `_` |
| `\W` | Non-word | anything except word chars |
| `\s` | Whitespace | space, tab, newline |
| `\S` | Non-whitespace | anything except whitespace |

## Reference: All Quantifiers

| Quantifier | Means | Examples |
|-----------|-------|----------|
| `a?` | 0 or 1 times | `a` optional |
| `a*` | 0 or more times | `aaa` allowed |
| `a+` | 1 or more times | minimum 1 `a` |
| `a{n}` | Exactly n times | `a{3}` = `aaa` |
| `a{n,}` | n or more times | `a{2,}` = `aa...` |
| `a{n,m}` | Between n and m | `a{2,5}` = 2 to 5 `a`s |

---

**Visual Guide Last Updated:** November 20, 2024
