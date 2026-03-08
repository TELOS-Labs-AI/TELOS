# TELOS Observatory V3 - Design System Documentation

## Executive Summary

The TELOS Observatory is built on a sophisticated dark-theme design system centered around a refined gold (#F4D03F) color palette, Streamlit's native component library, and CSS-based styling injections. The design system uses a zone-based color system that correlates directly with fidelity metrics (alignment scoring) and includes both static CSS variables and dynamic color functions.

**Key Design Principles:**
- Dark theme for focus and reduced eye strain
- Color-to-fidelity mapping for intuitive user feedback
- Glassmorphism effects for elevated container surfaces
- 8px spacing grid system for consistency
- Accessibility-first approach (44px touch targets, WCAG 1.4.8 line-height)

---

## Part 1: Color Branding System

### 1.1 Primary Brand Color

```python
# config/colors.py - Single source of truth
GOLD = '#F4D03F'  # Refined gold - primary brand color
```

**Usage:**
- Page borders and accents
- Active button states
- Header highlights
- Steward panel accents
- Warning/important indicators

**RGB Equivalent:** RGB(244, 208, 63)

### 1.2 Status Colors (Fidelity Zones)

The color system maps directly to fidelity scores representing user alignment with their stated purpose:

```python
# config/colors.py
# Zone Thresholds (Fidelity-based classification)

STATUS_GOOD     = '#27ae60'   # GREEN - Aligned zone (≥0.70)
STATUS_MILD     = '#f39c12'   # YELLOW - Minor Drift (0.60-0.69)
STATUS_MODERATE = '#e67e22'   # ORANGE - Drift Detected (0.50-0.59)
STATUS_SEVERE   = '#e74c3c'   # RED - Significant Drift (<0.50)
```

**Zone Legend (always visible to users):**
```html
<div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">
    <span style="color: #27ae60;">● Aligned (70%+)</span>
    <span style="color: #f39c12;">● Minor Drift (60-69%)</span>
    <span style="color: #e67e22;">● Drift (50-59%)</span>
    <span style="color: #e74c3c;">● Severe (<50%)</span>
</div>
```

**Application:**
- Button borders change based on context fidelity
- Gauge meter colors
- Trajectory chart markers
- Alert background tints
- Component borders (primary interface)

### 1.3 Background Colors (Dark Theme)

```python
# config/colors.py
BG_BASE     = '#0d0d0d'    # Darkest - base layer (nearly black)
BG_SURFACE  = '#1a1a1a'    # Primary surface for containers
BG_ELEVATED = '#2d2d2d'    # Elevated/card surface for interactive elements
BG_OVERLAY  = '#3a3a3a'    # Modal/overlay surface (top layer)
```

**Usage Pattern:**
- `BG_BASE`: Page background (often overridden by gradient)
- `BG_SURFACE`: Main content containers, sidebar
- `BG_ELEVATED`: Buttons, interactive elements, card surfaces
- `BG_OVERLAY`: Modals, popups, Steward panel backgrounds

**Gradient Glassmorphism (Applied at page load):**
```css
background:
    radial-gradient(ellipse 90% 90% at 15% 5%, rgba(244, 208, 63, 0.7) 0%, transparent 40%),
    radial-gradient(ellipse 80% 80% at 90% 95%, rgba(200, 160, 40, 0.6) 0%, transparent 35%),
    radial-gradient(ellipse 60% 60% at 50% 50%, rgba(244, 180, 63, 0.4) 0%, transparent 50%),
    linear-gradient(135deg, #1a1510 0%, #0d0a05 50%, #0a0805 100%);
```

### 1.4 Text Colors

```python
# config/colors.py
TEXT_PRIMARY   = '#e0e0e0'   # Primary text (85% brightness gray)
TEXT_SECONDARY = '#b0b0b0'   # Secondary text (69% brightness gray)
TEXT_MUTED     = '#808080'   # Muted/disabled text (50% brightness gray)
```

**Contrast Ratios (WCAG AAA):**
- Primary on BG_BASE: 14:1
- Primary on BG_ELEVATED: 12:1
- Secondary on BG_ELEVATED: 8:1

### 1.5 Opacity Variations (Hierarchy Function)

```python
# config/colors.py
def with_opacity(color: str, opacity: float) -> str:
    """Add opacity to a hex color."""
    hex_color = color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {opacity})'

# Gold opacity hierarchy
GOLD_100 = GOLD                    # #F4D03F (100% - headers)
GOLD_80  = with_opacity(GOLD, 0.8) # rgba(244, 208, 63, 0.8) - borders
GOLD_60  = with_opacity(GOLD, 0.6) # rgba(244, 208, 63, 0.6) - accents
GOLD_40  = with_opacity(GOLD, 0.4) # rgba(244, 208, 63, 0.4) - subtle hints
```

### 1.6 Color Mapping Functions

**Primary function: Dynamic fidelity-to-color mapping**

```python
def get_fidelity_color(score) -> str:
    """Map fidelity score to zone color."""
    score = _normalize_score(score)  # Handles %s, 0.75, 75 formats
    if score >= 0.70:
        return STATUS_GOOD      # '#27ae60' (green)
    elif score >= 0.60:
        return STATUS_MILD      # '#f39c12' (yellow)
    elif score >= 0.50:
        return STATUS_MODERATE  # '#e67e22' (orange)
    else:
        return STATUS_SEVERE    # '#e74c3c' (red)

# Example usage
color = get_fidelity_color(0.75)  # Returns '#27ae60'
color = get_fidelity_color('75%') # Returns '#27ae60' (auto-normalized)
```

**Secondary functions:**

```python
def get_color_name(score) -> str:
    """Get color name instead of hex."""
    # Returns: 'green', 'yellow', 'orange', 'red'

def get_zone_name(score) -> str:
    """Get human-friendly zone name."""
    # Returns: 'Aligned', 'Minor Drift', 'Drift Detected', 'Significant Drift'

def format_fidelity_percent(score) -> str:
    """Format fidelity as percentage."""
    # Returns: '75%', '100%', etc.

def format_fidelity_display(score) -> str:
    """Format with percentage and grade."""
    # Returns: '75% (B)', '95% (A+)', etc.

def get_letter_grade(score) -> str:
    """Get academic-style letter grade."""
    # Returns: 'A+', 'A', 'B-', 'C', 'D', 'F'
```

---

## Part 2: CSS Design System

### 2.1 CSS Variables (Root Context)

Defined in main.py's initial markdown injection:

```css
:root {
    /* Spacing scale (8px grid) */
    --space-xs: 4px;    /* Tight - between related items */
    --space-sm: 8px;    /* Default - standard gap */
    --space-md: 16px;   /* Moderate - between sections */
    --space-lg: 24px;   /* Generous - between major sections */
    --space-xl: 32px;   /* Maximum - page sections */

    /* Colors - Single source of truth */
    --color-gold: #F4D03F;
    --color-gold-dim: rgba(244, 208, 63, 0.5);
    --color-green: #27ae60;
    --color-yellow: #f39c12;
    --color-orange: #e67e22;
    --color-red: #e74c3c;

    /* Backgrounds */
    --bg-dark: #0a0a0a;
    --bg-surface: #1a1a1a;
    --bg-elevated: #2d2d2d;
    --bg-hover: #3d3d3d;

    /* Text */
    --text-primary: #e0e0e0;
    --text-secondary: #b0b0b0;
    --text-muted: #808080;
}
```

### 2.2 Button Styling Pattern

**Standard Button (applies to all `<button>` elements):**

```css
.stButton > button,
button[data-baseweb="button"] {
    background-color: #2d2d2d !important;
    color: #e0e0e0 !important;
    border: 1px solid #F4D03F !important;
    transition: all 0.3s ease !important;
    text-align: center !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    border-radius: 8px !important;
}

/* Hover state - elevated appearance */
.stButton > button:hover {
    background-color: #3d3d3d !important;
    border-width: 2px !important;
    border-color: #F4D03F !important;
    box-shadow: 0 0 8px rgba(244, 208, 63, 0.5) !important;
    transform: scale(1.02) !important;
}

/* Focus state (keyboard navigation) */
.stButton > button:focus {
    outline: none !important;
    box-shadow: 0 0 10px rgba(244, 208, 63, 0.6) !important;
}

/* Active state (pressed) */
.stButton > button:active {
    transform: scale(0.98) !important;
}
```

**Dynamic Fidelity Button (changes color based on context):**

```css
/* When rendering Alignment Lens button with user fidelity color */
.alignment-lens-btn-marker + div button {
    background-color: #2d2d2d !important;
    border: 2px solid {fidelity_color} !important;  /* Dynamically injected */
    color: #e0e0e0 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}

.alignment-lens-btn-marker + div button:hover {
    background-color: #3d3d3d !important;
    box-shadow: 0 0 12px {fidelity_color} !important;
}
```

**WCAG Touch Target Compliance (44px minimum):**

```css
.stButton > button {
    aspect-ratio: 1 !important;
    min-width: 44px !important;
    min-height: 44px !important;
    padding: 0 !important;
}

/* Responsive breakpoints */
@media (max-width: 768px) {
    .stButton > button {
        min-width: 44px !important;
        min-height: 44px !important;
        font-size: 12px !important;
    }
}
```

### 2.3 Container & Card Styling

**Main Content Container:**

```css
.main .block-container {
    max-width: 950px !important;      /* Max width for readability */
    margin-left: auto !important;     /* Center on page */
    margin-right: auto !important;
    padding: 20px !important;
    border: 1px solid #F4D03F;        /* Gold accent border */
    border-radius: 10px !important;
    background-color: transparent !important;  /* Shows gradient beneath */
}

/* Responsive width reduction */
@media (max-width: 1000px) {
    .main .block-container {
        max-width: 700px !important;
        width: 100% !important;
    }
}
```

**Glassmorphic Card (Steward Panel, Message Containers):**

```css
.card-glassmorphic {
    background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.08) 0%,
        rgba(255, 255, 255, 0.03) 50%,
        transparent 100%
    ), rgba(26, 26, 30, 0.45);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 2px solid #F4D03F;        /* Gold border for primary */
    border-radius: 10px;
    padding: 15px;
    box-shadow: 
        0 0 15px rgba(244, 208, 63, 0.15),  /* Gold glow */
        0 8px 32px rgba(0, 0, 0, 0.3),      /* Drop shadow */
        inset 0 1px 1px rgba(255, 255, 255, 0.1);  /* Rim light */
}

/* Secondary card (user message) */
.card-secondary {
    border-color: #666 !important;
}
```

**Observatory Lens Header:**

```css
.observatory-header {
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
    border: 2px solid #F4D03F;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    margin-bottom: 20px;
}

.observatory-header h2 {
    color: #F4D03F;
    margin: 0;
    font-weight: bold;
    letter-spacing: 2px;
}
```

### 2.4 Form & Input Styling

**Text Input:**

```css
.stTextInput input {
    background-color: #2d2d2d !important;
    color: #ffffff !important;
    border: 1px solid #F4D03F !important;
    border-radius: 6px !important;
    padding: 10px 12px !important;
}

.stTextInput input:focus {
    border-color: #F4D03F !important;
    outline: none !important;
    box-shadow: 0 0 4px rgba(244, 208, 63, 0.5) !important;
}

.stTextInput input::placeholder {
    color: #888 !important;
}
```

**Text Area (Message input):**

```css
.stTextArea textarea {
    background-color: #2d2d2d !important;
    color: #ffffff !important;
    border: 1px solid #F4D03F !important;
    border-radius: 6px !important;
    font-family: inherit !important;
    font-size: 16px !important;
}

.stTextArea textarea:focus {
    border-color: #F4D03F !important;
    box-shadow: 0 0 4px rgba(244, 208, 63, 0.5) !important;
    outline: none !important;
}
```

**Checkbox Toggle (Custom):**

```css
.stCheckbox input[type="checkbox"] {
    width: 44px !important;
    height: 24px !important;
    appearance: none !important;
    -webkit-appearance: none !important;
    background-color: #2d2d2d !important;
    border: 2px solid #666 !important;
    border-radius: 12px !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    position: relative !important;
}

/* Unchecked state */
.stCheckbox input[type="checkbox"]::after {
    content: "";
    position: absolute;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background-color: #fff;
    top: 2px;
    left: 2px;
    transition: all 0.3s ease;
}

/* Checked state */
.stCheckbox input[type="checkbox"]:checked {
    background-color: #F4D03F !important;
    border-color: #F4D03F !important;
}

.stCheckbox input[type="checkbox"]:checked::after {
    left: 22px;
    background-color: #0a0a0a;
}
```

### 2.5 Tabs Styling

```css
.stTabs [data-baseweb="tab-list"] {
    gap: 10px;
    background-color: #1a1a1a;
    border-bottom: 1px solid #333;
}

/* Inactive tab */
.stTabs [data-baseweb="tab"] {
    background-color: #2d2d2d;
    border: 1px solid #F4D03F;
    border-radius: 8px 8px 0 0;
    color: #e0e0e0;
    font-size: 22px;
    font-weight: bold;
    padding: 12px 24px;
    transition: all 0.2s ease;
}

/* Active tab */
.stTabs [aria-selected="true"] {
    background-color: #F4D03F;
    color: #0a0a0a;
    font-weight: bold;
    box-shadow: 0 0 8px rgba(244, 208, 63, 0.5);
}
```

### 2.6 Animation Styles

**Button Blink Animation (on page load):**

```css
@keyframes quickBlink {
    0% { opacity: 1; }
    85% { opacity: 1; }
    90% { box-shadow: 0 0 8px #F4D03F; }
    95% { box-shadow: none; }
    100% { opacity: 1; }
}

.stButton > button {
    animation: quickBlink 1.4s ease-in-out;
}
```

**Sidebar Slide-In Animation:**

```css
@keyframes slideInFromLeft {
    0% {
        transform: translateX(-100%);
        opacity: 0;
    }
    100% {
        transform: translateX(0);
        opacity: 1;
    }
}

[data-testid="stSidebar"] {
    animation: slideInFromLeft 1.2s ease-out;
}
```

**Steward Contemplating Pulse:**

```css
@keyframes steward-border-pulse {
    0%, 100% {
        border-color: #888;
        box-shadow: 0 0 6px rgba(136, 136, 136, 0.3);
    }
    50% {
        border-color: #F4D03F;
        box-shadow: 0 0 6px rgba(244, 208, 63, 0.4);
    }
}

.steward-contemplating-border {
    animation: steward-border-pulse 2s ease-in-out infinite;
}
```

**Copy Button Success State:**

```css
/* Dynamically applied via JavaScript */
button.copy-success {
    border-color: #27ae60 !important;
    color: #27ae60 !important;
    background: rgba(76, 175, 80, 0.15) !important;
    transition: all 0.2s ease;
}
```

### 2.7 Responsive Layout System

**Two-column layout (Steward panel open):**

```css
/* When Steward panel is open: 70% main | 30% panel */
.main .block-container {
    width: 100% !important;
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* Column widths */
[data-testid="stColumn"]:nth-child(1) {
    flex: 7;  /* 70% main content */
}

[data-testid="stColumn"]:nth-child(2) {
    flex: 3;  /* 30% Steward panel */
}
```

**Single-column layout (Steward panel closed):**

```css
/* When Steward panel is closed: centered 700px */
.main .block-container {
    max-width: 700px !important;
    width: 100% !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding: 1rem !important;
}
```

**Full-width action buttons:**

```css
/* Tab and action button rows */
[data-testid="stHorizontalBlock"] {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    gap: 8px !important;
}

/* Action button columns (50% each) */
[data-testid="stColumn"] {
    flex: 1 1 calc(50% - 4px) !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
```

---

## Part 3: UI Component Patterns

### 3.1 Component Naming Conventions

**File naming:**
- PascalCase for class names: `ConversationDisplay`, `BetaObservationDeck`
- snake_case for file names: `conversation_display.py`, `beta_observation_deck.py`
- Component files always include a class with `.render()` method

**Class structure pattern:**

```python
class ComponentName:
    """Clear description of component purpose."""
    
    def __init__(self, dependencies):
        """Initialize component with required dependencies."""
        self.dependency = dependency
    
    def render(self):
        """Main render method - called from main.py."""
        # Layout logic
        # Data collection
        # st.markdown() calls for styling
        # st.button() calls
        
    def _private_helper_method(self):
        """Private methods start with underscore."""
        # Implementation
```

### 3.2 Container Pattern

All major containers follow a consistent pattern:

```python
def render_container():
    # 1. Header with icon, title, and subtitle
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
        border: 2px solid #F4D03F;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    ">
        <h2 style="color: #F4D03F; margin: 0;">🔭 CONTAINER TITLE</h2>
        <p style="color: #888; font-size: 12px; margin: 5px 0 0 0;">Subtitle</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Divider
    st.markdown("---")
    
    # 3. Content area
    # (columns, buttons, metrics, etc.)
    
    # 4. Close/collapse button (if expandable)
    if st.button("✕ Close", key="unique_key"):
        # Handle close logic
```

### 3.3 Message Container Pattern (Glassmorphism)

```python
def render_message(content: str, role: str = 'assistant'):
    """Render a single message with glassmorphic styling."""
    if role == 'assistant':
        border_color = '#F4D03F'  # Gold for Steward
    else:
        border_color = '#666'     # Gray for user
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.08) 0%,
            rgba(255, 255, 255, 0.03) 50%,
            transparent 100%
        ), rgba(26, 26, 30, 0.45);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 2px solid {border_color};
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 
            0 0 15px rgba(244, 208, 63, 0.15),
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 1px rgba(255, 255, 255, 0.1);
    ">
        <span style="color: #e0e0e0; font-size: 20px; line-height: 1.6;">
            {html.escape(content)}
        </span>
    </div>
    """, unsafe_allow_html=True)
```

### 3.4 Zone-Colored Badge Pattern

Used for fidelity displays throughout the app:

```python
def render_fidelity_badge(fidelity: float, label: str = None):
    """Render a fidelity-colored badge."""
    from config.colors import get_fidelity_color, get_zone_name
    
    color = get_fidelity_color(fidelity)
    zone = get_zone_name(fidelity)
    display = label or f"{int(fidelity * 100)}%"
    
    st.markdown(f"""
    <div style="
        display: inline-block;
        background: #2d2d2d;
        border: 1px solid {color};
        border-radius: 4px;
        padding: 6px 12px;
        color: {color};
        font-size: 13px;
        font-weight: 600;
    ">
        {display}
    </div>
    """, unsafe_allow_html=True)
```

### 3.5 Grid Layout Pattern

Two-column layouts are common throughout:

```python
col1, col2 = st.columns([3, 1])  # 75% | 25% split

with col1:
    # Main content
    pass

with col2:
    # Secondary content (metrics, icons, etc.)
    pass
```

Three-column layouts for tabs/navigation:

```python
col_demo, col_beta, col_telos = st.columns(3)

with col_demo:
    if st.button("DEMO", key="tab_demo", use_container_width=True):
        st.session_state.active_tab = "DEMO"
        st.rerun()
```

---

## Part 4: Styling Conventions

### 4.1 CSS Injection Strategy

All styling in TELOS is injected via `st.markdown(..., unsafe_allow_html=True)` at render time:

```python
# Pattern 1: Global style block
st.markdown("""
<style>
/* CSS rules */
</style>
""", unsafe_allow_html=True)

# Pattern 2: Inline styles on elements
st.markdown("""
<div style="
    background-color: #2d2d2d;
    border: 1px solid #F4D03F;
    padding: 10px;
">Content</div>
""", unsafe_allow_html=True)

# Pattern 3: Dynamic styles (f-string injection)
color = get_fidelity_color(0.75)
st.markdown(f"""
<div style="border-color: {color};">
    Dynamic content
</div>
""", unsafe_allow_html=True)
```

**CSS Specificity Strategy:**

1. Low specificity for basic styling (class selectors)
2. High specificity for overrides (element + attribute + class)
3. `!important` used for critical Streamlit overrides
4. Late-stage injection for highest priority (end of render)

```python
# High-specificity selector example
st.markdown("""
<style>
/* Target specific Streamlit containers with maximum specificity */
.main .block-container div[data-testid="stHorizontalBlock"] button {
    background-color: #2d2d2d !important;
    border: 1px solid #F4D03F !important;
}
</style>
""", unsafe_allow_html=True)
```

### 4.2 Border Styling Convention

All borders follow a consistent pattern:

```
border: {width} solid {color}
```

**Standard widths:**
- `1px` - Subtle borders, secondary elements
- `2px` - Primary borders, interactive elements
- `3px` - Emphasis, active states

**Standard colors:**
- `#F4D03F` - Primary (active, important)
- Zone colors (`#27ae60`, `#f39c12`, etc.) - Status-specific
- `#666` - Secondary, neutral
- `#333` - Tertiary, very subtle

**Examples:**

```css
/* Primary button - active */
border: 2px solid #F4D03F;

/* User message - neutral */
border: 1px solid #666;

/* Steward message - brand accent */
border: 2px solid #F4D03F;

/* Fidelity zone indicator - dynamic */
border: 1px solid {get_fidelity_color(score)};

/* Emphasis state */
border: 3px solid #F4D03F;
box-shadow: 0 0 12px {fidelity_color};
```

### 4.3 Padding & Margin Convention

Uses the CSS variable scale (8px base grid):

```css
/* Padding (internal spacing) */
padding: 10px;         /* xs - 1.25 grid units */
padding: 12px;         /* sm - 1.5 grid units */
padding: 15px;         /* md - near 2 grid units */
padding: 20px;         /* lg - 2.5 grid units */

/* Margin (external spacing) */
margin: 4px;           /* xs - 0.5 grid units */
margin: 8px;           /* sm - 1 grid unit */
margin: 15px;          /* md - ~2 grid units */
margin: 20px;          /* lg - 2.5 grid units */

/* Layout spacing */
gap: 8px;              /* Between elements in flex/grid */
gap: 12px;             /* Larger gaps for visual separation */
margin-top: 0;         /* Remove Streamlit defaults */
margin-bottom: 0;      /* Remove Streamlit defaults */
```

### 4.4 Border Radius Convention

```css
border-radius: 3px;    /* Subtle, micro-interactions */
border-radius: 6px;    /* Standard, inputs, small containers */
border-radius: 8px;    /* Buttons, cards, medium containers */
border-radius: 10px;   /* Large containers, panels */
border-radius: 50%;    /* Circles (avatars, dots) */
border-radius: 12px;   /* Rounded toggles, pills */
```

**Examples:**

```css
/* Button */
border-radius: 8px;

/* Input field */
border-radius: 6px;

/* Card container */
border-radius: 10px;

/* Circular indicator */
border-radius: 50%;
width: 10px;
height: 10px;
```

### 4.5 Shadow & Glow Convention

```css
/* Subtle drop shadow (default for cards) */
box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);

/* Rim light (glassmorphic effect) */
box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);

/* Gold glow (emphasis) */
box-shadow: 0 0 8px rgba(244, 208, 63, 0.5);

/* Compound shadow (glassmorphic + glow) */
box-shadow:
    0 0 15px rgba(244, 208, 63, 0.15),
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.1);

/* Hover/focus glow */
box-shadow: 0 0 12px {fidelity_color};
```

---

## Part 5: Layout Structure

### 5.1 Page Layout Architecture

```
┌─────────────────────────────────────────┐
│          GRADIENT BACKGROUND            │
│    (Glassmorphism: gold + dark)         │
├─────────────────────────────────────────┤
│  ┌──────────────────────────────────┐   │
│  │    MAIN CONTENT CONTAINER        │   │
│  │  (max-width: 950px, centered)    │   │
│  │                                  │   │
│  │  ┌─────────────────────────────┐ │   │
│  │  │  Tab Navigation (DEMO/BETA) │ │   │
│  │  └─────────────────────────────┘ │   │
│  │                                  │   │
│  │  ┌─────────────────────────────┐ │   │
│  │  │  Page-Specific Content      │ │   │
│  │  │  (Conversation, Deck, etc.) │ │   │
│  │  └─────────────────────────────┘ │   │
│  │                                  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**Max-width breakpoints:**
- Desktop (>1000px): 950px
- Tablet (768-1000px): 700px
- Mobile (<768px): 100% (with padding)

### 5.2 DEMO Page Layout

```
┌──────────────────────────────────────┐
│  Demo Slide (with embedded Deck)     │
│  - Progressive slideshow system       │
│  - Embedded Observation Deck (slide 4)│
│  - Custom controls per slide         │
└──────────────────────────────────────┘
```

### 5.3 BETA Page Layout (Steward closed)

```
┌──────────────────────────────────────┐
│  Conversation Display                │
│  - ChatGPT-style turn-by-turn        │
│  - Message containers with borders   │
│  - Input box at bottom               │
├──────────────────────────────────────┤
│  "Show Alignment Lens" Button        │
├──────────────────────────────────────┤
│  Beta Observation Deck               │
│  - User/AI/Primacy State gauges      │
│  - Fidelity trajectory chart         │
│  - Intervention status               │
└──────────────────────────────────────┘
```

### 5.4 BETA Page Layout (Steward open)

```
┌─────────────────────────────────┬──────────────┐
│  Conversation (70% width)       │ Steward (30%)│
│  - Messages                     │              │
│  - Input box                    │ Chat history │
│                                 │ Message input│
│                                 │              │
│  Observation Deck               │ Contemplating│
│  - Alignment Lens               │ animation    │
│  - TELOSCOPE panel              │              │
└─────────────────────────────────┴──────────────┘
```

**Responsive behavior:**
- On mobile: Stack vertically (100% width each)
- Steward panel always remains 30% width on desktop
- Message containers scale with parent width

### 5.5 Sidebar Structure (TELOS mode)

```
┌─────────────────┐
│  🔭 LOGO        │
│  [Title]        │
├─────────────────┤
│  Status Badge   │
│  (Beta/TELOS)   │
├─────────────────┤
│  [Buttons]      │
│  - Observatory  │
│  - Links        │
│  - Profile      │
├─────────────────┤
│  Progress Bars  │
│  - Turns        │
│  - Feedback     │
└─────────────────┘
```

---

## Part 6: Typography & Fonts

### 6.1 Font Stack (System Default)

TELOS uses the browser's default system font stack for performance:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
```

No custom fonts are loaded - all CSS uses `inherit` for font-family.

### 6.2 Font Sizes

All sizes are set via CSS injection in main.py:

```css
/* Base size */
html, body {
    font-size: 16px !important;
}

/* Specific elements */
h1 { font-size: 36px !important; }
h2 { font-size: 30px !important; }
h3 { font-size: 24px !important; }
h4 { font-size: 20px !important; }
p, span { font-size: 16px !important; }
button { font-size: 16px !important; }
input { font-size: 16px !important; }
label { font-size: 16px !important; }

/* Smaller text */
.label-small { font-size: 12px; }
.text-muted { font-size: 12px; }
```

**Typography scale:**
- `12px` - Small labels, muted text
- `14px` - Tab labels, small buttons
- `16px` - Body text, buttons
- `20px` - Subheadings
- `24px` - Section headings
- `30px` - Page headings
- `36px` - Main title

### 6.3 Font Weight Convention

```css
font-weight: 400;  /* Regular - body text */
font-weight: 600;  /* Semi-bold - badges, labels */
font-weight: 700;  /* Bold - headings, emphasis */
font-weight: bold; /* Bold - alternative (auto-resolves to 700) */
```

### 6.4 Line Height (WCAG 1.4.8 compliance)

```css
body, html, .stMarkdown, .stText, span, div {
    line-height: 1.5 !important;
}

/* For code/technical text */
code, pre {
    line-height: 1.4;
}
```

**Rationale:** 1.5 line height improves readability for users with dyslexia and low vision.

### 6.5 Letter Spacing

```css
.header-main {
    letter-spacing: 2px;  /* For titles/headings only */
}

/* No letter-spacing on body text */
p, span { letter-spacing: normal; }
```

---

## Part 7: Reusable Styling Functions

### 7.1 Python Styling Utilities

**Color function:**

```python
from config.colors import get_fidelity_color, with_opacity

# Get color for a fidelity score
color = get_fidelity_color(0.75)  # Returns '#27ae60'

# Add opacity to a color
rgba = with_opacity('#F4D03F', 0.5)  # Returns 'rgba(244, 208, 63, 0.5)'
```

**Glow color conversion (from teloscope_panel.py):**

```python
def _get_glow_color(hex_color: str, opacity: float = 0.4) -> str:
    """Convert hex color to rgba glow."""
    if not hex_color or hex_color == "None":
        return f"rgba(102, 102, 102, {opacity})"
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    try:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {opacity})"
    except ValueError:
        return f"rgba(102, 102, 102, {opacity})"
```

**Markdown to HTML conversion (common in components):**

```python
def _md_to_html(text: str) -> str:
    """Convert basic markdown to HTML."""
    text = html.escape(text)
    
    # Zone-colored scores: [[green:0.856]] -> colored span
    def replace_zone_score(match):
        zone = match.group(1)
        value = match.group(2)
        color = ZONE_COLORS.get(zone, '#F4D03F')
        return f'<span style="color: {color}; font-weight: bold;">{value}</span>'
    
    text = re.sub(r'\[\[(\w+):([^\]]+)\]\]', replace_zone_score, text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<code style="background: rgba(0,0,0,0.3); padding: 2px 4px; border-radius: 3px;">\1</code>', text)
    text = text.replace('\n', '<br>')
    return text
```

### 7.2 CSS Utility Classes

While TELOS primarily uses inline styles, some utility patterns emerge:

```css
/* Spacing utilities */
.margin-top-sm { margin-top: 8px; }
.margin-top-md { margin-top: 16px; }
.margin-bottom-sm { margin-bottom: 8px; }
.margin-bottom-md { margin-bottom: 16px; }

/* Text utilities */
.text-gold { color: #F4D03F; }
.text-primary { color: #e0e0e0; }
.text-secondary { color: #b0b0b0; }
.text-center { text-align: center; }
.text-bold { font-weight: 600; }

/* Container utilities */
.container-glass {
    background: linear-gradient(...);
    border: 2px solid #F4D03F;
    border-radius: 10px;
    padding: 15px;
}

.container-elevated {
    background-color: #2d2d2d;
    border: 1px solid #F4D03F;
    border-radius: 8px;
    padding: 12px;
}
```

---

## Part 8: Accessibility Features

### 8.1 Color Contrast Requirements

TELOS meets WCAG AAA standards for all text:

```
TEXT_PRIMARY (#e0e0e0) on BG_BASE (#0d0d0d):     14:1 ✓ AAA
TEXT_PRIMARY (#e0e0e0) on BG_ELEVATED (#2d2d2d): 12:1 ✓ AAA
STATUS_GOOD (#27ae60) on BG_ELEVATED (#2d2d2d):  6.5:1 ✓ AA
```

### 8.2 Touch Target Sizing

All interactive elements meet WCAG 2.5.5 minimum 44px target:

```css
.stButton > button {
    min-width: 44px !important;
    min-height: 44px !important;
}

.turn-badge {
    aspect-ratio: 1;
    min-width: 44px;
    min-height: 44px;
}
```

### 8.3 Focus States

All buttons have visible focus indicators:

```css
button:focus {
    outline: none !important;
    box-shadow: 0 0 10px rgba(244, 208, 63, 0.6) !important;
}
```

### 8.4 Motion & Animation Preferences

While animations are used, they are subtle and can be dismissed:

```css
/* Smooth transitions (not jarring) */
transition: all 0.3s ease;
transition: box-shadow 0.2s ease;

/* Animations are non-essential (no prefers-reduced-motion override yet) */
/* Could be added: @media (prefers-reduced-motion: reduce) */
```

---

## Part 9: Design Tokens Summary

| Token | Value | Usage |
|-------|-------|-------|
| `--color-gold` | `#F4D03F` | Brand accent, active states |
| `--color-green` | `#27ae60` | Aligned/good status |
| `--color-yellow` | `#f39c12` | Minor drift status |
| `--color-orange` | `#e67e22` | Drift detected status |
| `--color-red` | `#e74c3c` | Severe drift status |
| `--bg-dark` | `#0a0a0a` | Page background |
| `--bg-surface` | `#1a1a1a` | Main surfaces |
| `--bg-elevated` | `#2d2d2d` | Interactive elements |
| `--bg-hover` | `#3d3d3d` | Hover states |
| `--text-primary` | `#e0e0e0` | Main text |
| `--text-secondary` | `#b0b0b0` | Secondary text |
| `--text-muted` | `#808080` | Disabled text |
| `--space-xs` | `4px` | Micro spacing |
| `--space-sm` | `8px` | Standard spacing |
| `--space-md` | `16px` | Section spacing |
| `--space-lg` | `24px` | Generous spacing |
| `--space-xl` | `32px` | Max spacing |

---

## Part 10: Component Design Patterns Summary

### 10.1 Pattern: Simple Button

```python
if st.button("Label", key="unique_key", use_container_width=True):
    # Handle click
    st.session_state.flag = True
    st.rerun()
```

**Auto-applied CSS:**
- Dark background (#2d2d2d)
- Gold border (#F4D03F)
- Hover glow effect
- 44px minimum size

### 10.2 Pattern: Fidelity-Colored Button

```python
from config.colors import get_fidelity_color

color = get_fidelity_color(user_fidelity)
st.markdown(f"""
<style>
.my-button-marker + div button {{
    border: 2px solid {color} !important;
    box-shadow: 0 0 12px {color} !important;
}}
</style>
<div class="my-button-marker" style="display:none;"></div>
""", unsafe_allow_html=True)

if st.button("Dynamic Color Button"):
    # Click handler
```

### 10.3 Pattern: Glassmorphic Container

```python
st.markdown(f"""
<div style="
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
">
    Content here
</div>
""", unsafe_allow_html=True)
```

### 10.4 Pattern: Metric Badge

```python
from config.colors import get_fidelity_color, format_fidelity_percent

fidelity = 0.75
color = get_fidelity_color(fidelity)
percent = format_fidelity_percent(fidelity)

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
    {percent}
</span>
""", unsafe_allow_html=True)
```

---

## Usage Examples

### Example 1: Creating a Fidelity-Aware Button

```python
from config.colors import get_fidelity_color

def render_custom_button(label: str, fidelity: float):
    color = get_fidelity_color(fidelity)
    
    st.markdown(f"""
    <style>
    .custom-btn-{id(label)} + div button {{
        border: 2px solid {color} !important;
        background-color: #2d2d2d !important;
        color: #e0e0e0 !important;
    }}
    </style>
    <div class="custom-btn-{id(label)}" style="display:none;"></div>
    """, unsafe_allow_html=True)
    
    return st.button(label, use_container_width=True)
```

### Example 2: Adding a New Component

```python
# components/my_component.py
from config.colors import GOLD, get_fidelity_color
import streamlit as st

class MyComponent:
    def __init__(self):
        pass
    
    def render(self):
        # Header
        st.markdown(f"""
        <div style="
            border: 2px solid {GOLD};
            border-radius: 10px;
            padding: 20px;
        ">
            <h2 style="color: {GOLD};">Component Title</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Content
        if st.button("Action", use_container_width=True):
            st.session_state.action = True
            st.rerun()
```

---

## Final Notes

1. **Single Source of Truth**: All colors are defined in `config/colors.py`
2. **Dynamic Color Mapping**: Use `get_fidelity_color(score)` for all fidelity-based colors
3. **CSS Injection**: All styling is injected at render time via `st.markdown(unsafe_allow_html=True)`
4. **Specificity Strategy**: Use high-specificity selectors for Streamlit overrides
5. **Responsive Design**: Max-width adjusts based on content width and sidebar state
6. **Accessibility**: All interactive elements meet WCAG AAA standards
7. **Glassmorphism**: Standard for elevated surfaces, adds visual sophistication
8. **Component Patterns**: Consistent across 27+ component files in `components/`

