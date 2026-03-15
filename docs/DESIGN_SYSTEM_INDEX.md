# TELOS Observatory V3 - Design System Documentation Index

## Overview

This directory contains comprehensive design system documentation for the TELOS Observatory V3 Streamlit application. The design system encompasses color branding, CSS patterns, UI component architecture, and accessibility guidelines.

## Documents

### 1. **DESIGN_SYSTEM.md** (Main Document)
**Size:** 38KB | **1,429 lines**

Comprehensive design system specification covering:

- **Part 1: Color Branding System** (6 sections)
  - Primary brand color (#F4D03F gold)
  - Status colors for fidelity zones (green/yellow/orange/red)
  - Background colors for dark theme
  - Text colors with WCAG contrast ratios
  - Opacity variations and hierarchy
  - Color mapping functions

- **Part 2: CSS Design System** (7 sections)
  - CSS variables and root context
  - Button styling patterns
  - Container and card styling (glassmorphism)
  - Form and input styling
  - Tabs, animations
  - Responsive layout system

- **Part 3: UI Component Patterns** (5 sections)
  - Component naming conventions
  - Container patterns
  - Message containers (glassmorphic)
  - Zone-colored badges
  - Grid layout patterns

- **Part 4: Styling Conventions** (5 sections)
  - CSS injection strategy
  - Border styling conventions
  - Padding and margin grid
  - Border radius scale
  - Shadow and glow effects

- **Part 5: Layout Structure** (5 sections)
  - Page layout architecture
  - DEMO page layout
  - BETA page layouts (Steward closed/open)
  - Sidebar structure

- **Part 6: Typography & Fonts**
  - System font stack
  - Font sizes and weights
  - Line height (1.5 for WCAG 1.4.8)
  - Letter spacing

- **Part 7: Reusable Styling Functions**
  - Python styling utilities
  - CSS utility classes

- **Part 8: Accessibility Features**
  - Color contrast requirements (WCAG AAA)
  - Touch target sizing (WCAG 2.5.5)
  - Focus states
  - Motion and animation preferences

- **Part 9: Design Tokens Summary**
  - Complete token reference table

- **Part 10: Component Design Patterns Summary**
  - Common patterns with code examples

### 2. **DESIGN_SYSTEM_QUICK_REFERENCE.md** (Quick Reference)
**Size:** 9.1KB

Quick lookup guide organized by topic:

- **Color Palette Table** - All hex codes and RGB values
- **Essential CSS Patterns** - Button, cards, containers, inputs
- **Key Functions** - Color mapping functions reference
- **Spacing Grid** - 8px-based spacing scale
- **Border Styles** - Radius, width, and color conventions
- **Typography Table** - Sizes, weights, line heights
- **Animations** - Keyframe definitions
- **Layout Breakpoints** - Responsive design thresholds
- **Accessibility Checklist** - WCAG standards
- **Component File Locations** - Where to find each component
- **CSS Injection Pattern** - How to add custom styles
- **Common Patterns** - Copy-paste code examples
- **Troubleshooting Guide** - Solutions to common issues

## Key Files Analyzed

### Color & Styling Configuration
- **`config/colors.py`** - Color definitions, fidelity functions
- **`config/steward_styles.py`** - Steward persona styling (6 bands)
- **`telos_observatory_v3/main.py`** - Global CSS (2,041 lines)

### UI Components (27 files analyzed)
Key components include:
- `conversation_display.py` - Message rendering with copy buttons
- `beta_observation_deck.py` - Alignment Lens and status displays
- `beta_steward_panel.py` - Steward chat interface with glassmorphism
- `alignment_indicator.py` - Fidelity status indicator
- `observatory_lens.py` - Real-time governance visualization
- `teloscope_panel.py` - Research instrument view
- `intervention_evidence_dashboard.py` - Governance evidence browser
- `sidebar_actions_beta.py` - Sidebar controls and progress

## Design System Highlights

### Color Palette
| Color | Hex | Usage |
|-------|-----|-------|
| Gold (Brand) | #F4D03F | Primary accent, buttons, borders |
| Green (Aligned) | #27ae60 | Fidelity ≥0.70 |
| Yellow (Minor Drift) | #f39c12 | Fidelity 0.60-0.69 |
| Orange (Drift) | #e67e22 | Fidelity 0.50-0.59 |
| Red (Severe) | #e74c3c | Fidelity <0.50 |

### Core Design Principles
1. **Dark Theme** - Reduces eye strain, professional appearance
2. **Fidelity-Driven Coloring** - Colors directly represent alignment scores
3. **Glassmorphism** - Modern elevated surfaces with transparency and blur
4. **8px Grid System** - Consistent spacing throughout
5. **WCAG Accessibility** - AAA contrast ratios, 44px touch targets
6. **Responsive Design** - Adaptive layouts for all screen sizes

### CSS Injection Strategy
- All styling via `st.markdown(unsafe_allow_html=True)`
- CSS variables defined at page load
- Late-stage injection for highest specificity
- `!important` used strategically for Streamlit overrides
- Adjacent sibling selectors for dynamic button coloring

### Component Architecture
- **Consistent Pattern**: Each component has `.render()` method
- **File Naming**: PascalCase classes, snake_case files
- **Styling**: All CSS via inline styles or markdown injection
- **Interactivity**: Streamlit buttons with session state

## Fidelity Zones

The entire design system maps to user alignment scores:

| Zone | Fidelity | Color | Meaning | Intervention |
|------|----------|-------|---------|--------------|
| GREEN | ≥0.70 | #27ae60 | Aligned | None |
| YELLOW | 0.60-0.69 | #f39c12 | Minor Drift | Light |
| ORANGE | 0.50-0.59 | #e67e22 | Drift Detected | Moderate |
| RED | <0.50 | #e74c3c | Significant Drift | Strong |

## CSS Patterns Summary

### Button (Standard)
- Background: #2d2d2d (elevated)
- Border: 1px solid #F4D03F (gold)
- Hover: Background #3d3d3d, 2px border, 8px glow
- Size: 44px minimum (WCAG)

### Card (Glassmorphic)
- Gradient overlay with 8% opacity white
- Backdrop blur: 10px
- Border: 2px solid #F4D03F
- Shadow: Drop + rim light + glow
- Padding: 15px

### Container
- Max-width: 950px (desktop), 700px (tablet)
- Centered with auto margins
- Gold border accent
- Transparent background (shows gradient behind)

### Input
- Background: #2d2d2d
- Text: white
- Border: 1px solid #F4D03F
- Focus: Glow with 4px shadow

## Layout System

### Breakpoints
- **Desktop (>1000px)**: 950px max-width
- **Tablet (768-1000px)**: 700px max-width
- **Mobile (<768px)**: 100% with padding

### Steward Panel States
- **Closed**: 700px centered single column
- **Open**: 70/30 split (main/panel)
- **Mobile**: Full-width stacked

## Accessibility Features

### Color Contrast
- TEXT_PRIMARY (#e0e0e0) on BG_BASE (#0d0d0d): 14:1 (AAA)
- TEXT_PRIMARY (#e0e0e0) on BG_ELEVATED (#2d2d2d): 12:1 (AAA)
- All status colors: 12:1+ on dark backgrounds

### Touch Targets
- Buttons: 44px × 44px minimum
- Turn badges: 40px × 40px minimum
- Responsive scaling on mobile

### Motion
- All transitions: 0.2s-0.3s ease
- Animations: Subtle, non-jarring
- Supports smooth scrolling

## Usage Examples

### Adding a New Component
```python
from config.colors import get_fidelity_color
import streamlit as st

class MyComponent:
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def render(self):
        # Use get_fidelity_color() for dynamic colors
        color = get_fidelity_color(user_fidelity)
        
        # Inject CSS with f-strings
        st.markdown(f"""
        <style>
        .my-component {{
            border: 2px solid {color};
            border-radius: 10px;
        }}
        </style>
        """, unsafe_allow_html=True)
        
        # Render content
        st.button("Action")
```

### Using Color Functions
```python
from config.colors import (
    get_fidelity_color,      # Score -> hex
    get_zone_name,           # Score -> "Aligned"
    format_fidelity_percent, # Score -> "75%"
    with_opacity             # Hex + opacity -> rgba()
)

color = get_fidelity_color(0.75)        # Returns '#27ae60'
zone = get_zone_name(0.75)              # Returns 'Aligned'
pct = format_fidelity_percent(0.75)     # Returns '75%'
rgba = with_opacity('#F4D03F', 0.5)    # Returns 'rgba(244, 208, 63, 0.5)'
```

## Project Statistics

- **Total Components**: 27 component files
- **Total Lines of Python**: 17,120+ lines (components only)
- **CSS Lines**: ~2,000+ in main.py
- **Color Functions**: 9 utility functions
- **Animations**: 3 main animations (blink, pulse, slide)
- **Responsive Breakpoints**: 3 major breakpoints
- **WCAG Standards**: AAA color contrast, 2.5.5 touch targets

## Related Documentation

- **CLAUDE.md** - Development guide and technical reference
- **TELOS_Whitepaper_v2.3.md** - Mathematical specification
- **TELOS_Lexicon_V1.1.md** - Terminology definitions
- **GRANT_ROADMAP.md** - Funding and consortium architecture

## How to Use These Documents

### For Designers
- Start with **DESIGN_SYSTEM_QUICK_REFERENCE.md**
- Reference color table and essential patterns
- Use component file locations for browsing
- Check layout breakpoints for responsive work

### For Developers
- Reference **DESIGN_SYSTEM.md** for detailed specifications
- Use CSS patterns from Part 2 and Part 4
- Follow component patterns from Part 3
- Check accessibility requirements in Part 8

### For New Contributors
1. Read **DESIGN_SYSTEM_QUICK_REFERENCE.md** (5 min)
2. Explore **component file locations** table
3. Review **common patterns** section
4. Reference **DESIGN_SYSTEM.md** for specifics

### For Maintenance
- Check **Part 9: Design Tokens Summary** for updates
- Review **Part 8: Accessibility** for compliance
- Reference **Part 7** for reusable functions
- Monitor responsive breakpoints in **Part 5**

## Contact & Questions

For questions about the design system:
1. Check **troubleshooting guide** in quick reference
2. Search **DESIGN_SYSTEM.md** for specific topic
3. Review existing components for patterns
4. Reference **CLAUDE.md** for development patterns

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-02 | Initial comprehensive documentation |

---

**Generated**: January 2, 2025
**Scope**: TELOS Observatory V3 Streamlit Application
**Status**: Complete and comprehensive

For full specifications, see **DESIGN_SYSTEM.md** (38KB)
For quick lookup, see **DESIGN_SYSTEM_QUICK_REFERENCE.md** (9.1KB)
