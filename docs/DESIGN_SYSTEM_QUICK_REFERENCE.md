# TELOS Observatory V3 - Design System Quick Reference

## Color Palette

### Primary Colors
| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Gold (Brand) | #F4D03F | RGB(244, 208, 63) | Borders, buttons, accents |
| Green (Aligned) | #27ae60 | RGB(39, 174, 96) | Fidelity ≥0.70 |
| Yellow (Minor Drift) | #f39c12 | RGB(243, 156, 18) | Fidelity 0.60-0.69 |
| Orange (Drift) | #e67e22 | RGB(230, 126, 34) | Fidelity 0.50-0.59 |
| Red (Severe) | #e74c3c | RGB(231, 76, 60) | Fidelity <0.50 |

### Background Colors
| Name | Hex | Usage |
|------|-----|-------|
| BG_BASE | #0d0d0d | Page background |
| BG_SURFACE | #1a1a1a | Main containers |
| BG_ELEVATED | #2d2d2d | Buttons, interactive |
| BG_OVERLAY | #3a3a3a | Modals, panels |

### Text Colors
| Name | Hex | Contrast |
|------|-----|----------|
| TEXT_PRIMARY | #e0e0e0 | 14:1 on BG_BASE |
| TEXT_SECONDARY | #b0b0b0 | 8:1+ |
| TEXT_MUTED | #808080 | Disabled/hints |

---

## Essential CSS Patterns

### Button
```css
.stButton > button {
    background-color: #2d2d2d !important;
    color: #e0e0e0 !important;
    border: 1px solid #F4D03F !important;
    border-radius: 8px !important;
    transition: all 0.3s ease !important;
    min-width: 44px !important;
    min-height: 44px !important;
}

.stButton > button:hover {
    background-color: #3d3d3d !important;
    border-color: #F4D03F !important;
    box-shadow: 0 0 8px rgba(244, 208, 63, 0.5) !important;
}
```

### Glassmorphic Card
```css
.card {
    background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.08) 0%,
        rgba(255, 255, 255, 0.03) 50%,
        transparent 100%
    ), rgba(26, 26, 30, 0.45);
    backdrop-filter: blur(10px);
    border: 2px solid #F4D03F;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 
        0 0 15px rgba(244, 208, 63, 0.15),
        0 8px 32px rgba(0, 0, 0, 0.3),
        inset 0 1px 1px rgba(255, 255, 255, 0.1);
}
```

### Container
```css
.main .block-container {
    max-width: 950px !important;
    margin: 0 auto !important;
    border: 1px solid #F4D03F;
    border-radius: 10px !important;
    padding: 20px !important;
}
```

### Text Input
```css
.stTextInput input {
    background-color: #2d2d2d !important;
    color: #ffffff !important;
    border: 1px solid #F4D03F !important;
    border-radius: 6px !important;
}

.stTextInput input:focus {
    border-color: #F4D03F !important;
    box-shadow: 0 0 4px rgba(244, 208, 63, 0.5) !important;
}
```

### Fidelity-Colored Element
```python
from config.colors import get_fidelity_color
color = get_fidelity_color(score)  # Returns #27ae60, #f39c12, #e67e22, or #e74c3c
```

---

## Key Functions

### Color Mapping
```python
from config.colors import (
    get_fidelity_color,      # Score -> hex color
    get_zone_name,           # Score -> 'Aligned', 'Minor Drift', etc.
    format_fidelity_percent, # Score -> '75%'
    format_fidelity_display, # Score -> '75% (B)'
    get_letter_grade,        # Score -> 'A+', 'B', 'C', etc.
    with_opacity             # Hex + opacity -> rgba()
)
```

### Component Pattern
```python
class MyComponent:
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def render(self):
        # Render method always called from main.py
        # Use st.markdown() for all styling
        # Use st.button() for interactions
```

---

## Spacing Grid (8px base)

| Variable | Value | Usage |
|----------|-------|-------|
| --space-xs | 4px | Micro spacing |
| --space-sm | 8px | Standard gap |
| --space-md | 16px | Section spacing |
| --space-lg | 24px | Generous spacing |
| --space-xl | 32px | Maximum spacing |

---

## Border Radius
- `3px` - Subtle micro-interactions
- `6px` - Input fields, small containers
- `8px` - Buttons, cards
- `10px` - Large containers, panels
- `12px` - Rounded pills, toggles
- `50%` - Circles

---

## Border Widths & Colors
- `1px solid #F4D03F` - Primary border
- `1px solid #666` - Secondary border
- `2px solid #F4D03F` - Active/emphasis border
- `3px solid #F4D03F` - Strong emphasis
- `1px solid {fidelity_color}` - Dynamic fidelity color

---

## Typography

### Font Stack (System default)
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

### Sizes
| Element | Size | Weight |
|---------|------|--------|
| h1 | 36px | bold |
| h2 | 30px | bold |
| h3 | 24px | bold |
| h4 | 20px | semi-bold |
| body/p | 16px | regular |
| button | 16px | semi-bold |
| label | 14px | semi-bold |
| small | 12px | regular |

### Line Height
- Body: 1.5 (WCAG 1.4.8 compliance)
- Code: 1.4

---

## Animations

### Button Blink (on load)
```css
@keyframes quickBlink {
    0%, 85% { opacity: 1; }
    90% { box-shadow: 0 0 8px #F4D03F; }
    95% { box-shadow: none; }
    100% { opacity: 1; }
}
```

### Steward Contemplating
```css
@keyframes steward-border-pulse {
    0%, 100% { border-color: #888; box-shadow: 0 0 6px rgba(136, 136, 136, 0.3); }
    50% { border-color: #F4D03F; box-shadow: 0 0 6px rgba(244, 208, 63, 0.4); }
}
```

### Sidebar Slide-In
```css
@keyframes slideInFromLeft {
    0% { transform: translateX(-100%); opacity: 0; }
    100% { transform: translateX(0); opacity: 1; }
}
[data-testid="stSidebar"] {
    animation: slideInFromLeft 1.2s ease-out;
}
```

---

## Layout Breakpoints

| Screen Size | Max-Width | Behavior |
|-------------|-----------|----------|
| Desktop (>1000px) | 950px | Centered with max-width |
| Tablet (768-1000px) | 700px | Responsive shrinking |
| Mobile (<768px) | 100% | Full width with padding |

### Steward Panel States
- **Closed**: 700px centered layout
- **Open**: 70% main + 30% panel (full width)
- **Mobile**: Stacked vertically

---

## Accessibility

### Color Contrast (WCAG AAA)
- TEXT_PRIMARY (#e0e0e0) on BG_BASE (#0d0d0d): 14:1 ✓
- TEXT_PRIMARY (#e0e0e0) on BG_ELEVATED (#2d2d2d): 12:1 ✓
- All interactive text on dark: 12:1+ minimum

### Touch Targets (WCAG 2.5.5)
- All buttons: 44px × 44px minimum
- Turn badges: 40px × 40px minimum
- Responsive scaling on mobile

### Motion
- All transitions: 0.2s-0.3s ease (non-jarring)
- Animations: Subtle, non-essential
- No prefers-reduced-motion override yet (TODO)

---

## Component File Locations

| Component | File | Key Methods |
|-----------|------|-------------|
| Conversation | `conversation_display.py` | `.render()` |
| Observation Deck | `beta_observation_deck.py` | `.render()` |
| Steward Panel | `beta_steward_panel.py` | `.render_panel()` |
| Alignment Indicator | `alignment_indicator.py` | `.render()` |
| Observatory Lens | `observatory_lens.py` | `.render()` |
| TELOSCOPE Panel | `teloscope_panel.py` | `.render()` |
| Sidebar | `sidebar_actions_beta.py` | `.render()` |

---

## CSS Injection Pattern

All styling is injected via `st.markdown()`:

```python
# 1. Global styles
st.markdown("""
<style>
/* CSS rules */
</style>
""", unsafe_allow_html=True)

# 2. Inline HTML with styles
st.markdown(f"""
<div style="color: {color}; border: 2px solid {color};">
    Content
</div>
""", unsafe_allow_html=True)

# 3. Using adjacent sibling selector for button styling
st.markdown(f"""
<style>
.marker + div button {{
    border: 2px solid {color} !important;
}}
</style>
<div class="marker" style="display:none;"></div>
""", unsafe_allow_html=True)
if st.button("Label"):
    # Button now has custom color
```

---

## Common Patterns

### Fidelity-Aware Badge
```python
from config.colors import get_fidelity_color, format_fidelity_percent

fidelity = 0.75
color = get_fidelity_color(fidelity)
pct = format_fidelity_percent(fidelity)

st.markdown(f"""
<span style="
    background: #2d2d2d;
    border: 1px solid {color};
    border-radius: 4px;
    padding: 6px 12px;
    color: {color};
    font-weight: 600;
    font-size: 13px;
">
    {pct}
</span>
""", unsafe_allow_html=True)
```

### Message Container
```python
role = 'assistant'  # or 'user'
border_color = '#F4D03F' if role == 'assistant' else '#666'

st.markdown(f"""
<div style="
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, ...),
                rgba(26, 26, 30, 0.45);
    backdrop-filter: blur(10px);
    border: 2px solid {border_color};
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 0 15px rgba(244, 208, 63, 0.15),
                0 8px 32px rgba(0, 0, 0, 0.3);
">
    {message_text}
</div>
""", unsafe_allow_html=True)
```

---

## Troubleshooting

### Colors not appearing?
- Check `config/colors.py` for hex values
- Use f-strings for dynamic colors
- Ensure no typos in color names

### CSS not applying?
- Use `!important` for Streamlit overrides
- Check selector specificity
- Inject CSS AFTER content (later = higher priority)

### Layout broken?
- Check max-width constraints
- Verify column ratios sum correctly
- Use `use_container_width=True` for buttons

### Touch targets too small?
- Ensure min-width: 44px and min-height: 44px
- Add `aspect-ratio: 1` for square buttons
- Test on mobile devices

---

## Files Reference

| File | Purpose |
|------|---------|
| `telos_observatory/main.py` | Global CSS variables, page layout |
| `config/colors.py` | Color definitions and functions |
| `config/steward_styles.py` | Steward persona styling |
| `components/*.py` | Individual UI components (27 files) |

---

Last updated: 2025-01-02
Full documentation: See `DESIGN_SYSTEM.md`
