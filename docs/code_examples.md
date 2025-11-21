# Chord Detection - Code Implementation Examples

This document provides working code examples for detecting chords in multiple programming languages.

## JavaScript / TypeScript

### Basic Implementation

```javascript
// Simple chord detection in American notation
function detectChords(text) {
  const chordPattern = /\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;
  return text.match(chordPattern) || [];
}

const text = "Play C major, then F, and finish with G7. Try Am7 next.";
console.log(detectChords(text));
// Output: ['C', 'F', 'G7', 'Am7']
```

### With False Positive Protection

```javascript
// Chord detection with negative lookahead to prevent matching common words
function detectChordsStrict(text) {
  const chordPattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;
  return text.match(chordPattern) || [];
}

const text = "I am playing C major. Are you ready? Add some F to make it interesting.";
console.log(detectChordsStrict(text));
// Output: ['C', 'F'] (correctly excludes 'am', 'Are', 'Add')
```

### With Position Information

```javascript
// Returns chord matches with their positions in the text
function detectChordsWithPositions(text) {
  const chordPattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;

  const matches = [];
  let match;

  while ((match = chordPattern.exec(text)) !== null) {
    matches.push({
      chord: match[0],
      position: match.index,
      endPosition: match.index + match[0].length
    });
  }

  return matches;
}

const text = "Start with C, move to F, then G7.";
console.log(detectChordsWithPositions(text));
// Output: [
//   { chord: 'C', position: 11, endPosition: 12 },
//   { chord: 'F', position: 22, endPosition: 23 },
//   { chord: 'G7', position: 30, endPosition: 32 }
// ]
```

### Chord Validator Class

```javascript
class ChordValidator {
  constructor() {
    this.chordPattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;
    this.validRoots = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
    this.validQualities = ['m', 'maj', 'min', '7', '9', '11', '13', '6', 'sus', 'dim', 'aug', 'add'];
  }

  detect(text) {
    return text.match(this.chordPattern) || [];
  }

  isValidChord(chord) {
    // Check if chord matches pattern
    return this.chordPattern.test(chord);
  }

  extractRoot(chord) {
    const rootMatch = chord.match(/^([A-G])/);
    return rootMatch ? rootMatch[1] : null;
  }

  extractAccidental(chord) {
    const accidentalMatch = chord.match(/^[A-G]([#b])/);
    return accidentalMatch ? accidentalMatch[1] : null;
  }

  extractQuality(chord) {
    const quality = chord.replace(/^[A-G][#b]?/, '');
    return quality || 'major';
  }

  findProgression(text) {
    // Find sequences of chords separated by dashes or spaces
    const progressionPattern = /(?:\b[A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*\b\s*[-–—]?\s*)+/g;
    return text.match(progressionPattern) || [];
  }
}

// Usage
const validator = new ChordValidator();

console.log(validator.detect("Play C, Dm7, and Gmaj7"));
// ['C', 'Dm7', 'Gmaj7']

console.log(validator.extractRoot("C#m7"));
// 'C'

console.log(validator.extractAccidental("C#m7"));
// '#'

console.log(validator.extractQuality("C#m7"));
// 'm7'

console.log(validator.findProgression("Progression: C - F - G - C"));
// ['C - F - G - C']
```

---

## Python

### Basic Implementation

```python
import re

def detect_chords(text):
    """Detect chords in American notation from text."""
    chord_pattern = r'\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
    return re.findall(chord_pattern, text)

text = "Play C major, then F, and finish with G7. Try Am7 next."
print(detect_chords(text))
# Output: ['C', 'F', 'G7', 'Am7']
```

### With False Positive Protection

```python
import re

def detect_chords_strict(text):
    """Detect chords with protection against common words."""
    chord_pattern = r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
    return re.findall(chord_pattern, text)

text = "I am playing C major. Are you ready? Add some F to make it interesting."
print(detect_chords_strict(text))
# Output: ['C', 'F']
```

### With Position Information and Span

```python
import re

def detect_chords_with_positions(text):
    """Detect chords with their positions in the text."""
    chord_pattern = r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'

    matches = []
    for match in re.finditer(chord_pattern, text):
        matches.append({
            'chord': match.group(0),
            'position': match.start(),
            'end_position': match.end()
        })

    return matches

text = "Start with C, move to F, then G7."
print(detect_chords_with_positions(text))
# Output:
# [
#   {'chord': 'C', 'position': 11, 'end_position': 12},
#   {'chord': 'F', 'position': 22, 'end_position': 23},
#   {'chord': 'G7', 'position': 30, 'end_position': 32}
# ]
```

### Chord Validator Class

```python
import re
from typing import List, Optional, Dict

class ChordValidator:
    def __init__(self):
        self.chord_pattern = r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
        self.root_pattern = r'^([A-G])'
        self.accidental_pattern = r'^[A-G]([#b])'

        self.valid_roots = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        self.valid_qualities = ['m', 'maj', 'min', '7', '9', '11', '13', '6', 'sus', 'dim', 'aug', 'add']

    def detect(self, text: str) -> List[str]:
        """Detect all chords in text."""
        return re.findall(self.chord_pattern, text)

    def is_valid_chord(self, chord: str) -> bool:
        """Check if a string is a valid chord."""
        return bool(re.match(self.chord_pattern, chord))

    def extract_root(self, chord: str) -> Optional[str]:
        """Extract the root note from a chord."""
        match = re.match(self.root_pattern, chord)
        return match.group(1) if match else None

    def extract_accidental(self, chord: str) -> Optional[str]:
        """Extract accidental (sharp/flat) from a chord."""
        match = re.search(self.accidental_pattern, chord)
        return match.group(1) if match else None

    def extract_quality(self, chord: str) -> str:
        """Extract quality (minor, 7th, etc.) from a chord."""
        quality = re.sub(r'^[A-G][#b]?', '', chord)
        return quality if quality else 'major'

    def parse_chord(self, chord: str) -> Dict[str, Optional[str]]:
        """Parse a chord into components."""
        return {
            'full_chord': chord,
            'root': self.extract_root(chord),
            'accidental': self.extract_accidental(chord),
            'quality': self.extract_quality(chord),
            'is_valid': self.is_valid_chord(chord)
        }

    def find_progressions(self, text: str) -> List[str]:
        """Find chord progressions (sequences of chords)."""
        progression_pattern = r'(?:\b[A-G](?:[#b])?(?:m(?:aj)?(?:\d+)?|min|maj7|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*\b\s*[-–—]?\s*)+'
        return re.findall(progression_pattern, text)

# Usage
validator = ChordValidator()

print(validator.detect("Play C, Dm7, and Gmaj7"))
# ['C', 'Dm7', 'Gmaj7']

print(validator.parse_chord("C#m7"))
# {
#     'full_chord': 'C#m7',
#     'root': 'C',
#     'accidental': '#',
#     'quality': 'm7',
#     'is_valid': True
# }

print(validator.extract_root("C#m7"))
# 'C'

print(validator.extract_accidental("C#m7"))
# '#'

print(validator.extract_quality("C#m7"))
# 'm7'

print(validator.find_progressions("Progression: C - F - G - C"))
# ['C - F - G - C ']
```

### European Notation Support

```python
import re
from typing import List

class EuropeanChordValidator:
    def __init__(self):
        self.european_pattern = r'\b((?:Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
        self.american_pattern = r'\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'

    def detect_american(self, text: str) -> List[str]:
        """Detect American notation chords."""
        return re.findall(self.american_pattern, text)

    def detect_european(self, text: str) -> List[str]:
        """Detect European notation chords."""
        return re.findall(self.european_pattern, text)

    def detect_both(self, text: str) -> Dict[str, List[str]]:
        """Detect both American and European notation."""
        return {
            'american': self.detect_american(text),
            'european': self.detect_european(text)
        }

# Usage
validator = EuropeanChordValidator()

print(validator.detect_american("Play C, Dm, and G7"))
# ['C', 'Dm', 'G7']

print(validator.detect_european("Jouez Do, Dom et Sol7"))
# ['Do', 'Dom', 'Sol7']

print(validator.detect_both("Mixed: C and Do, Dm and Dom"))
# {
#     'american': ['C', 'Dm'],
#     'european': ['Do', 'Dom']
# }
```

---

## PHP

### Basic Implementation

```php
<?php

function detectChords($text) {
    $chordPattern = '/\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/';

    $matches = [];
    preg_match_all($chordPattern, $text, $matches);

    return $matches[0] ?? [];
}

$text = "Play C major, then F, and finish with G7. Try Am7 next.";
print_r(detectChords($text));
// Output: Array ( [0] => C [1] => F [2] => G7 [3] => Am7 )

?>
```

### With False Positive Protection

```php
<?php

function detectChordsStrict($text) {
    $chordPattern = '/\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/';

    $matches = [];
    preg_match_all($chordPattern, $text, $matches);

    return $matches[0] ?? [];
}

$text = "I am playing C major. Are you ready? Add some F to make it interesting.";
print_r(detectChordsStrict($text));
// Output: Array ( [0] => C [1] => F )

?>
```

### Chord Validator Class

```php
<?php

class ChordValidator {
    private $chordPattern = '/\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/';

    private $validRoots = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
    private $validQualities = ['m', 'maj', 'min', '7', '9', '11', '13', '6', 'sus', 'dim', 'aug', 'add'];

    public function detect($text) {
        $matches = [];
        preg_match_all($this->chordPattern, $text, $matches);
        return $matches[0] ?? [];
    }

    public function isValidChord($chord) {
        return preg_match($this->chordPattern, $chord) === 1;
    }

    public function extractRoot($chord) {
        if (preg_match('/^([A-G])/', $chord, $matches)) {
            return $matches[1];
        }
        return null;
    }

    public function extractAccidental($chord) {
        if (preg_match('/^[A-G]([#b])/', $chord, $matches)) {
            return $matches[1];
        }
        return null;
    }

    public function extractQuality($chord) {
        $quality = preg_replace('/^[A-G][#b]?/', '', $chord);
        return $quality ?: 'major';
    }

    public function parseChord($chord) {
        return [
            'full_chord' => $chord,
            'root' => $this->extractRoot($chord),
            'accidental' => $this->extractAccidental($chord),
            'quality' => $this->extractQuality($chord),
            'is_valid' => $this->isValidChord($chord)
        ];
    }
}

// Usage
$validator = new ChordValidator();

print_r($validator->detect("Play C, Dm7, and Gmaj7"));
// Array ( [0] => C [1] => Dm7 [2] => Gmaj7 )

print_r($validator->parseChord("C#m7"));
// Array ( [full_chord] => C#m7 [root] => C [accidental] => # [quality] => m7 [is_valid] => 1 )

?>
```

---

## Java

### Basic Implementation

```java
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ChordDetector {
    private static final String CHORD_PATTERN =
        "\\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\\d)?(?:[b#]\\d+)*)\\b";

    private Pattern pattern;

    public ChordDetector() {
        this.pattern = Pattern.compile(CHORD_PATTERN);
    }

    public List<String> detectChords(String text) {
        List<String> chords = new ArrayList<>();
        Matcher matcher = pattern.matcher(text);

        while (matcher.find()) {
            chords.add(matcher.group(0));
        }

        return chords;
    }

    public static void main(String[] args) {
        ChordDetector detector = new ChordDetector();

        String text = "Play C major, then F, and finish with G7. Try Am7 next.";
        List<String> chords = detector.detectChords(text);

        System.out.println(chords);
        // Output: [C, F, G7, Am7]
    }
}
```

### Chord Validator Class

```java
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ChordValidator {
    private final Pattern chordPattern;
    private final Pattern rootPattern;
    private final Pattern accidentalPattern;

    public ChordValidator() {
        this.chordPattern = Pattern.compile(
            "\\b(?!am\\b|are\\b|and\\b|add\\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\\d)?(?:[b#]\\d+)*)\\b"
        );
        this.rootPattern = Pattern.compile("^([A-G])");
        this.accidentalPattern = Pattern.compile("^[A-G]([#b])");
    }

    public List<String> detect(String text) {
        List<String> chords = new ArrayList<>();
        Matcher matcher = chordPattern.matcher(text);

        while (matcher.find()) {
            chords.add(matcher.group(0));
        }

        return chords;
    }

    public boolean isValidChord(String chord) {
        return chordPattern.matcher(chord).find();
    }

    public String extractRoot(String chord) {
        Matcher matcher = rootPattern.matcher(chord);
        return matcher.find() ? matcher.group(1) : null;
    }

    public String extractAccidental(String chord) {
        Matcher matcher = accidentalPattern.matcher(chord);
        return matcher.find() ? matcher.group(1) : null;
    }

    public String extractQuality(String chord) {
        return chord.replaceAll("^[A-G][#b]?", "").isEmpty() ? "major" :
               chord.replaceAll("^[A-G][#b]?", "");
    }

    public Map<String, Object> parseChord(String chord) {
        Map<String, Object> result = new HashMap<>();
        result.put("full_chord", chord);
        result.put("root", extractRoot(chord));
        result.put("accidental", extractAccidental(chord));
        result.put("quality", extractQuality(chord));
        result.put("is_valid", isValidChord(chord));
        return result;
    }

    public static void main(String[] args) {
        ChordValidator validator = new ChordValidator();

        System.out.println(validator.detect("Play C, Dm7, and Gmaj7"));
        // Output: [C, Dm7, Gmaj7]

        System.out.println(validator.parseChord("C#m7"));
        // Output: {full_chord=C#m7, root=C, accidental=#, quality=m7, is_valid=true}
    }
}
```

---

## Testing and Validation

### Test Suite (JavaScript)

```javascript
// Test cases for chord detection
const testCases = [
  // American Notation - Should Match
  { input: "C", expected: ['C'], description: "C major" },
  { input: "Cm", expected: ['Cm'], description: "C minor" },
  { input: "C7", expected: ['C7'], description: "C dominant 7" },
  { input: "Cmaj7", expected: ['Cmaj7'], description: "C major 7" },
  { input: "Cm7b5", expected: ['Cm7b5'], description: "C minor 7 flat 5" },
  { input: "Csus4", expected: ['Csus4'], description: "C suspended 4" },
  { input: "Cadd9", expected: ['Cadd9'], description: "C add 9" },
  { input: "C#", expected: ['C#'], description: "C sharp" },
  { input: "Db", expected: ['Db'], description: "D flat" },

  // Should NOT Match
  { input: "I am here", expected: [], description: "Exclude 'am' verb" },
  { input: "You are great", expected: [], description: "Exclude 'are' verb" },
  { input: "We and they", expected: [], description: "Exclude 'and' conjunction" },

  // Mixed Content
  { input: "Play C then F and G7", expected: ['C', 'F', 'G7'], description: "Multiple chords with words" },
  { input: "The Am7 sounds great", expected: ['Am7'], description: "Chord with article" },
];

function runTests(testCases) {
  let passed = 0;
  let failed = 0;

  testCases.forEach(test => {
    const result = detectChordsStrict(test.input);
    const isPass = JSON.stringify(result) === JSON.stringify(test.expected);

    if (isPass) {
      passed++;
      console.log(`✓ ${test.description}`);
    } else {
      failed++;
      console.log(`✗ ${test.description}`);
      console.log(`  Input: "${test.input}"`);
      console.log(`  Expected: ${JSON.stringify(test.expected)}`);
      console.log(`  Got: ${JSON.stringify(result)}`);
    }
  });

  console.log(`\nResults: ${passed} passed, ${failed} failed`);
}

runTests(testCases);
```

---

## Performance Considerations

### Optimization Tips

1. **Compile Pattern Once**
   ```javascript
   // Good - compile once
   const chordPattern = /\b([A-G]...)\b/g;
   function detectChords(text) {
     return text.match(chordPattern);
   }
   ```

2. **Use Non-Capturing Groups**
   - `(?:...)` instead of `(...)` when you don't need to capture

3. **Lazy Quantifiers**
   - Use `*?` instead of `*` when appropriate for better performance

4. **Cache Results**
   ```javascript
   const cache = new Map();

   function detectChordsWithCache(text) {
     if (cache.has(text)) {
       return cache.get(text);
     }
     const result = detectChords(text);
     cache.set(text, result);
     return result;
   }
   ```

---

## Integration Examples

### React Component Example

```jsx
import React, { useState, useMemo } from 'react';

function ChordDetector() {
  const [text, setText] = useState('');

  const chordPattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;

  const chords = useMemo(() => {
    const matches = [];
    let match;
    const re = new RegExp(chordPattern.source, 'g');
    while ((match = re.exec(text)) !== null) {
      matches.push({
        text: match[0],
        index: match.index
      });
    }
    return matches;
  }, [text]);

  const highlightedText = () => {
    let lastIndex = 0;
    const parts = [];

    chords.forEach((chord, i) => {
      parts.push(text.substring(lastIndex, chord.index));
      parts.push(
        <span key={i} className="chord">
          {chord.text}
        </span>
      );
      lastIndex = chord.index + chord.text.length;
    });

    parts.push(text.substring(lastIndex));
    return parts;
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter chord progression..."
      />
      <div className="result">
        <h3>Detected Chords: {chords.length}</h3>
        <p>Chords: {chords.map(c => c.text).join(', ')}</p>
        <p className="highlighted">{highlightedText()}</p>
      </div>
    </div>
  );
}

export default ChordDetector;
```

### Express.js API Endpoint

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/api/detect-chords', (req, res) => {
  const { text } = req.body;

  if (!text || typeof text !== 'string') {
    return res.status(400).json({ error: 'Invalid input' });
  }

  const chordPattern = /\b(?!am\b|are\b|and\b|add\b)([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b/g;

  const chords = text.match(chordPattern) || [];

  res.json({
    input: text,
    chords: chords,
    count: chords.length,
    unique: [...new Set(chords)]
  });
});

app.listen(3000, () => {
  console.log('Chord detector API running on port 3000');
});
```

