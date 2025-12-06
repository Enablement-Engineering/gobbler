# Gobbler Brand Guidelines

> **Tagline:** *Connecting Your Information to Your Agents*

---

## Quick Reference

| Element | Value |
|---------|-------|
| Body Color | `#E8955C` Warm Orange |
| Feathers | `#8B5A2B` Chocolate Brown |
| Feather Accent | `#7FBCD2` Sky Blue |
| Outline | `#3D3224` Dark Brown |
| Background | `#FFFFFF` White |
| Font (Code) | System monospace / JetBrains Mono |
| Mascot Name | Gobby |
| Emoji | `🦃` |
| Default Port | `4625` ("GOBL" on phone keypad) |

### File Type Colors

| Type | Color | Hex |
|------|-------|-----|
| MD (Markdown) | Blue/Purple | `#6B7DB3` |
| PDF | Red | `#E74C3C` |
| HTML | Green | `#27AE60` |
| VIDEO | Teal | `#16A085` |
| AUDIO | Salmon/Pink | `#E8919A` |

---

## 1. Brand Identity

### The Concept

The internet is a messy buffet of spaghetti code, unformatted text, and bloated HTML. **Gobby** is the insatiable omnivore of the web. He doesn't just "parse" data—he slurps it, chews on the metadata, and digests it into clean, nutrient-dense Markdown.

He is wide-eyed, slightly confused by the complexity of the world, but singular in his purpose: **To Eat.**

### The Vibe

| Influence | Weight | Trait |
|-----------|--------|-------|
| Go Gopher | 50% | Helpful, flat, developer-native, open-source spirit |
| Gudetama | 30% | Existential, round, low center of gravity, "melting" into work |
| Pac-Man | 20% | Endless appetite for consuming data |

### Core Values

1. **Hungry** — Always ready to consume content
2. **Efficient** — Digests quickly, outputs cleanly
3. **Friendly** — Approachable, never intimidating
4. **Resilient** — Keeps eating even when things taste bad

---

## 2. Color System

### Gobby Palette (Mascot)

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Warm Orange** | `#E8955C` | `rgb(232, 149, 92)` | Body |
| **Chocolate Brown** | `#8B5A2B` | `rgb(139, 90, 43)` | Feathers (main) |
| **Sky Blue** | `#7FBCD2` | `rgb(127, 188, 210)` | Feathers (accent stripes) |
| **Dark Brown** | `#3D3224` | `rgb(61, 50, 36)` | Outlines |
| **Cream White** | `#FFFEF8` | `rgb(255, 254, 248)` | Eyes, highlights |

### File Type Colors

| Type | Hex | RGB | Usage |
|------|-----|-----|-------|
| **MD Blue** | `#6B7DB3` | `rgb(107, 125, 179)` | Markdown output files |
| **PDF Red** | `#E74C3C` | `rgb(231, 76, 60)` | PDF documents |
| **HTML Green** | `#27AE60` | `rgb(39, 174, 96)` | Web pages |
| **VIDEO Teal** | `#16A085` | `rgb(22, 160, 133)` | Video files |
| **AUDIO Pink** | `#E8919A` | `rgb(232, 145, 154)` | Audio files |

### UI Palette

| Name | Hex | Usage |
|------|-----|-------|
| **Success** | `#27AE60` | Completed, digested |
| **Warning** | `#F39C12` | Rate limited, retrying |
| **Error** | `#E74C3C` | Failed, choked |
| **Info** | `#3498DB` | Status messages |

### Semantic Colors

```css
:root {
  /* Gobby */
  --gobbler-body: #E8955C;
  --gobbler-feathers: #8B5A2B;
  --gobbler-feathers-accent: #7FBCD2;
  --gobbler-outline: #3D3224;

  /* File Types */
  --gobbler-md: #6B7DB3;
  --gobbler-pdf: #E74C3C;
  --gobbler-html: #27AE60;
  --gobbler-video: #16A085;
  --gobbler-audio: #E8919A;

  /* States */
  --gobbler-success: #27AE60;
  --gobbler-warning: #F39C12;
  --gobbler-error: #E74C3C;
  --gobbler-info: #3498DB;

  /* Text */
  --gobbler-text-primary: #3D3224;
  --gobbler-text-secondary: #6B6E8A;
  --gobbler-text-inverse: #FFFFFF;
}
```

---

## 3. Visual Identity

### Style

**Illustrated Cartoon** — Not flat vector. Gobby has personality through:

- Subtle shading for dimension
- Expressive eyes with eyebrows
- Dynamic poses
- Warm, friendly aesthetic

### Geometry Rules

| Element | Specification |
|---------|--------------|
| **Body** | Round, plump turkey shape. Short legs, small wings. |
| **Eyes** | Large white circles with black pupils. Can show emotion (wide=surprised, half-closed=content). One eye often larger for "derp" expression. |
| **Beak** | Small, orange, slightly curved. Opens wide when eating. |
| **Feathers** | Fan tail with brown feathers + sky blue accent stripes. Rounded tips. |
| **Proportions** | Eyes = 25-30% of head. Body is ~60% of total height. |

### Line Work

| Property | Value |
|----------|-------|
| Stroke weight | 2-3px at 100px height (scales proportionally) |
| Stroke color | `#3D3224` Dark Brown |
| End caps | Rounded |
| Corners | Rounded (no sharp angles) |
| Style | Consistent weight, slight variation allowed for expression |
| Shading | Subtle darker tones on undersides for dimension |

### Logo Sizes

| Context | Size | Format |
|---------|------|--------|
| Favicon | 16x16, 32x32 | PNG, ICO |
| Small icon | 48x48 | PNG, SVG |
| Medium icon | 128x128 | PNG, SVG |
| Large display | 256x256+ | SVG preferred |
| Social/OG | 1200x630 | PNG |

### Clear Space

Minimum clear space around logo = 25% of logo height on all sides.

```
┌─────────────────────┐
│                     │
│   ┌───────────┐     │
│   │   🦃      │     │
│   │  GOBBY    │     │
│   └───────────┘     │
│        ↑            │
│    25% height       │
└─────────────────────┘
```

---

## 4. Asset Specifications

### Directory Structure

```
assets/
├── logo/
│   ├── gobby-icon.svg          # Master vector
│   ├── gobby-icon-16.png
│   ├── gobby-icon-32.png
│   ├── gobby-icon-48.png
│   ├── gobby-icon-128.png
│   ├── gobby-icon-256.png
│   └── gobby-wordmark.svg      # Logo + "Gobbler" text
├── states/
│   ├── gobby-eating.svg        # Ingestion animation
│   ├── gobby-chewing.svg       # Processing state
│   ├── gobby-done.svg          # Success state
│   ├── gobby-error.svg         # Face-plant error
│   └── gobby-waiting.svg       # Idle/queue state
├── social/
│   ├── og-image.png            # 1200x630 Open Graph
│   ├── twitter-card.png        # 1200x600
│   └── github-social.png       # 1280x640
└── emoji/
    └── gobby-emoji-set.png     # Slack/Discord emoji pack
```

### File Format Guidelines

| Use Case | Format | Notes |
|----------|--------|-------|
| Icons, logos | SVG | Primary format, scalable |
| Favicons | PNG + ICO | Multi-resolution ICO for browsers |
| Social images | PNG | 72 DPI, sRGB color space |
| Animations | SVG + CSS or Lottie | No GIFs (large file size) |
| Print | PDF or SVG | CMYK color space for print |

---

## 5. Canonical Poses (Reference Sheet)

The following poses are the official Gobby expressions:

| Pose | Name | Use Case | Description |
|------|------|----------|-------------|
| **Top Left** | The Slurp | Ingestion/downloading | Beak wide open, eating file tape, outputting MD blocks |
| **Top Right** | The Chew | Processing/converting | File tape in beak, pulling it through like spaghetti |
| **Bottom Left** | The Zen Pile | Batch complete/success | Sitting contentedly on MD stack, dreaming of file types |
| **Bottom Right** | The Juggle | Multiple inputs/queue | Holding armful of colorful file icons, slightly overwhelmed |

### Visual Elements in Each Pose

- **Input tape**: Ribbon of colored file type labels (PDF=red, HTML=green, VIDEO=teal, AUDIO=pink)
- **Output blocks**: Blue/purple "MD" file icons
- **File icons**: Rounded rectangles with file type labels
- **Expressions**: Wide eyes=active, half-closed=content, spiral=error

---

## 6. AI Image Generation Prompts

### Base Style Prompt

Append to ALL image generation requests:

> **...in the style of a cute illustrated cartoon turkey mascot. Warm orange body, chocolate brown tail feathers with sky blue accent stripes. Dark brown outlines. Expressive eyes (large white circles with small pupils). Slight shading for dimension. Friendly and approachable. White background.**

### Scenario Prompts

#### A. "The Slurp" (Ingestion) ✅
>
> *A cute round turkey with wide surprised eyes, beak open wide, eating a long ribbon/tape of file icons. The tape has colored labels: "PDF" (red), "HTML" (green), "VIDEO" (teal), "AUDIO" (pink). Blue "MD" file icons are being output/spit out. Dynamic eating pose.* [+ Base Prompt]

#### B. "The Zen Pile" (Batch Processing) ✅
>
> *A content turkey with half-closed sleepy eyes, sitting on top of a neat pyramid stack of blue "MD" file blocks. A thought bubble above shows file type icons (.html .pdf .mp4 .mp3). Peaceful, accomplished expression.* [+ Base Prompt]

#### C. "The Chew" (Processing)
>
> *A turkey holding a ribbon of colorful file type labels in its beak, pulling them like spaghetti. Concentrated expression. File labels show "HTML", "PDF", "VIDEO", "AUDIO" in their brand colors.* [+ Base Prompt]

#### D. "The Juggle" (Multiple Inputs)
>
> *A slightly overwhelmed turkey juggling/holding multiple colorful file icons against its chest. Files labeled "HTML", "PDF", "VIDEO", "AUDIO" in brand colors. Wide-eyed expression, small sweat drop optional.* [+ Base Prompt]

#### E. "The Error" (Failure State)
>
> *A turkey lying face down, exhausted, with spiral eyes or X eyes. A single feather falls nearby. Comedic defeat pose.* [+ Base Prompt]

#### F. "The Hunter" (Web Scraping)
>
> *A turkey wearing a miner's helmet with headlamp. Peeking around a browser window frame. Sneaky/curious expression.* [+ Base Prompt]

---

## 7. Iconography System

### State Icons

| State | Icon | Emoji | Description |
|-------|------|-------|-------------|
| **Input** | Knife & fork | `🍴` | Ready to consume |
| **Processing** | Puffed cheeks | `😤` | Chewing/digesting |
| **Output** | MD brick | `📦` | Clean markdown output |
| **Success** | Code burp | `✅` | Digestion complete |
| **Error** | Face-plant | `😵` | Choked on input |
| **Queue** | Juggling | `🤹` | Multiple items pending |
| **Waiting** | Sleepy | `😴` | Idle, ready for food |

### Tool Icons

| Tool Category | Visual Metaphor |
|--------------|-----------------|
| YouTube | Gobby with headphones |
| Web scraping | Gobby with miner's helmet |
| Documents | Gobby with reading glasses |
| Audio | Gobby with ear trumpet |
| Batch | Gobby on pile of boxes |

---

## 8. Voice & Tone

### Principles

1. **Playful but professional** — Fun personality, serious functionality
2. **Food metaphors** — Everything relates to eating/digesting
3. **Brief** — Short, punchy messages
4. **Helpful** — Always tell the user what's happening

### Message Translation

| Standard | Gobbler Voice |
|----------|--------------|
| Processing complete | Digested. |
| Error: Could not parse URL | Choked on that link. Tasted like 404. |
| Waiting for input | Feed me. |
| Download started | Spotted prey... |
| Converting | Chewing... |
| File saved | Plated and served. |
| Queue empty | Stomach's empty. |
| Rate limited | Taking a food coma break. |

### CLI Output Format

```
Phase indicators:
🦃  [Action]... (Explanation)

Progress format:
🍽️  Digesting... [████████░░] 80%

Completion:
✅  Digested! Output: /path/to/file.md
```

### Example Session

```bash
$ gobbler transcribe https://youtube.com/watch?v=abc123

🦃  Spotting prey... (Found: "How to Cook Perfect Pasta")
🔪  Slicing content... (Downloading transcript)
🍽️  Digesting... [████████████] 100%
🦴  Spitting out bones... (Cleaning timestamps)
✅  Digested! Output: how-to-cook-perfect-pasta.md
    └── 2,847 words | 12 min read
```

### Error Messages

```bash
# Network error
😵 Choked! Couldn't reach that URL. Check your internet.

# Invalid input
🤢 Can't eat that. Expected a URL, got... whatever this is.

# Rate limited
😴 Food coma. YouTube said slow down. Retrying in 30s...

# Service down
💀 Crawl4AI container is sleeping. Run: make docker-up
```

---

## 9. Typography

### Font Stack

```css
/* Code and CLI */
font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;

/* Documentation headings */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Body text */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```

### Hierarchy

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| H1 | 2rem | 700 | Dark Brown `#3D3224` |
| H2 | 1.5rem | 600 | Dark Brown |
| H3 | 1.25rem | 600 | Dark Brown |
| Body | 1rem | 400 | Dark Brown |
| Code | 0.875rem | 400 | MD Blue `#6B7DB3` |
| Caption | 0.75rem | 400 | Dark Brown 60% |

---

## 10. Implementation Checklist

### README/Documentation

- [x] Logo at top of README
- [ ] Consistent color usage in badges
- [ ] Voice/tone matches guidelines
- [ ] Error messages use Gobbler voice

### CLI Output

- [ ] Emoji prefixes for state indication
- [ ] Progress bars use brand format
- [ ] Error messages are helpful + playful
- [ ] Success messages confirm output location

### Website/Docs Site

- [ ] CSS variables match color system
- [ ] Favicon set (16, 32, 48, 128)
- [ ] Open Graph image set
- [ ] Consistent typography

### Social Media

- [ ] Profile picture uses approved icon
- [ ] Banner uses brand colors
- [ ] Bio includes tagline

### Browser Extension

- [ ] Icons match brand (16, 48, 128)
- [ ] Popup uses brand colors
- [ ] Error states show Gobby states

---

## 11. Don'ts

| Don't | Why |
|-------|-----|
| Use realistic/photographic turkey | Gobby is illustrated cartoon style |
| Use sharp angular shapes | Everything is rounded and friendly |
| Change the feather colors | Brown + sky blue is the signature look |
| Mix Gobby with other mascots | Brand dilution |
| Use wrong file type colors | MD=blue, PDF=red, HTML=green, etc. |
| Make Gobby aggressive or scary | He's hungry, not angry |
| Forget the tail feathers | The brown/blue fan is distinctive |
| Use flat colors only | Subtle shading adds dimension |

---

## Appendix: CSS Variables (Copy-Paste Ready)

```css
:root {
  /* === GOBBLER BRAND SYSTEM === */

  /* Gobby Mascot */
  --gb-body: #E8955C;
  --gb-feathers: #8B5A2B;
  --gb-feathers-accent: #7FBCD2;
  --gb-outline: #3D3224;

  /* File Types */
  --gb-file-md: #6B7DB3;
  --gb-file-pdf: #E74C3C;
  --gb-file-html: #27AE60;
  --gb-file-video: #16A085;
  --gb-file-audio: #E8919A;

  /* UI States */
  --gb-success: #27AE60;
  --gb-warning: #F39C12;
  --gb-error: #E74C3C;
  --gb-info: #3498DB;

  /* Text */
  --gb-text: #3D3224;
  --gb-text-muted: #6B6E8A;
  --gb-text-inverse: #FFFFFF;

  /* Surfaces */
  --gb-surface: #FFFFFF;
  --gb-surface-elevated: #FAFAFA;
  --gb-border: #E0E0E0;

  /* Typography */
  --gb-font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --gb-font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Spacing */
  --gb-space-xs: 0.25rem;
  --gb-space-sm: 0.5rem;
  --gb-space-md: 1rem;
  --gb-space-lg: 1.5rem;
  --gb-space-xl: 2rem;

  /* Radii */
  --gb-radius-sm: 4px;
  --gb-radius-md: 8px;
  --gb-radius-lg: 16px;
  --gb-radius-full: 9999px;
}
```

---

*Last updated: December 2024*
