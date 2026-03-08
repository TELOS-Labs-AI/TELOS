"""
TELOSCOPE Profile Selector Component.

Three profiles optimized for different use cases:
1. General User - Simplified governance experience
2. Research - Full TELOSCOPE with data export and analysis tools
3. DevOps - System administration and monitoring
"""

from typing import Optional

import streamlit as st


# Profile definitions with feature flags
PROFILES = {
    "general": {
        "name": "General User",
        "icon": "person",
        "description": "AI governance for everyday conversations",
        "tagline": "Purpose-aligned AI assistance",
        "features": [
            "Primacy Attractor setup",
            "Real-time fidelity monitoring",
            "Steward guidance"
        ],
        "enabled": {
            "observation_deck": True,
            "observatory_lens": True,
            "teloscope_controls": False,
            "research_dashboard": False,
            "admin_controls": False,
            "data_export": False
        }
    },
    "research": {
        "name": "Research",
        "icon": "search",
        "description": "TELOSCOPE research instrument with full analytics",
        "tagline": "IRB-ready governance research",
        "features": [
            "Full TELOSCOPE timeline",
            "Session data export",
            "Convergence analysis",
            "Counterfactual branching",
            "Research briefs generation"
        ],
        "enabled": {
            "observation_deck": True,
            "observatory_lens": True,
            "teloscope_controls": True,
            "research_dashboard": True,
            "admin_controls": False,
            "data_export": True
        }
    },
    "devops": {
        "name": "DevOps",
        "icon": "terminal",
        "description": "System administration and monitoring",
        "tagline": "Full system access",
        "features": [
            "All research features",
            "Backend metrics",
            "System diagnostics",
            "Configuration controls"
        ],
        "enabled": {
            "observation_deck": True,
            "observatory_lens": True,
            "teloscope_controls": True,
            "research_dashboard": True,
            "admin_controls": True,
            "data_export": True
        }
    }
}


def get_profile_from_query_params() -> Optional[str]:
    """Check query params for profile selection.

    Admin/devops access requires TELOS_ADMIN_SECRET env var.
    """
    import os
    query_params = st.query_params

    # Direct profile param (non-privileged profiles only)
    profile = query_params.get("profile")
    if profile in PROFILES and profile not in ("devops",):
        return profile

    # Admin access requires secret
    admin_secret = os.environ.get("TELOS_ADMIN_SECRET", "")
    admin_token = query_params.get("admin", "")
    if admin_secret and admin_token and admin_secret == admin_token and len(admin_secret) >= 16:
        return "devops"

    if query_params.get("research") == "true":
        return "research"

    return None


def render_profile_selector() -> Optional[str]:
    """Render profile selection cards. Returns selected profile or None."""

    # Simple prompt without TELOSCOPE branding
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <p style="color: #888; font-size: 1.1em;">
            Select your observation profile
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Global styling for compact cards and gold-bordered features
    st.markdown("""
    <style>
    .compact-card {
        background: rgba(20, 20, 20, 0.95);
        border: 2px solid #333;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        width: 100%;
        aspect-ratio: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        max-height: 120px;
    }
    .compact-card:hover {
        border-color: #F4D03F;
        box-shadow: 0 0 15px rgba(244, 208, 63, 0.2);
    }
    .compact-icon {
        font-size: 32px;
        margin-bottom: 8px;
    }
    .compact-name {
        color: #F4D03F;
        font-size: 1.1em;
        font-weight: bold;
    }
    .feature-box {
        border: 1px solid #F4D03F;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0;
        background: rgba(244, 208, 63, 0.05);
    }
    .feature-text {
        color: #FFFFFF;
        font-size: 0.85em;
        margin: 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Create three columns for profile cards
    cols = st.columns(3)

    selected_profile = None

    for idx, (profile_key, profile) in enumerate(PROFILES.items()):
        with cols[idx]:
            # Icon mapping
            icon_map = {
                "person": "👤",
                "search": "🔬",
                "terminal": "⚙️"
            }
            icon = icon_map.get(profile["icon"], "📊")

            # Compact square card
            st.markdown(f"""
            <div class="compact-card">
                <div class="compact-icon">{icon}</div>
                <div class="compact-name">{profile['name']}</div>
            </div>
            """, unsafe_allow_html=True)

            # Gold bordered feature boxes
            for feature in profile["features"]:
                st.markdown(f"""
                <div class="feature-box">
                    <p class="feature-text">{feature}</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

            # Selection button
            if st.button(
                f"Select {profile['name']}",
                key=f"select_{profile_key}",
                use_container_width=True
            ):
                selected_profile = profile_key

    return selected_profile


def apply_profile_settings(profile_key: str) -> dict:
    """Apply profile settings to session state. Returns enabled features dict."""
    profile = PROFILES.get(profile_key, PROFILES["general"])

    # Store in session state
    st.session_state.teloscope_profile = profile_key
    st.session_state.teloscope_profile_name = profile["name"]
    st.session_state.teloscope_features = profile["enabled"]

    return profile["enabled"]


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled for current profile."""
    features = st.session_state.get("teloscope_features", {})
    return features.get(feature, False)


def get_current_profile() -> str:
    """Get current profile key. Defaults to 'general'."""
    return st.session_state.get("teloscope_profile", "general")


def render_profile_badge():
    """Render small badge showing current profile in sidebar/header."""
    profile_key = get_current_profile()
    profile = PROFILES.get(profile_key, PROFILES["general"])

    icon_map = {"person": "👤", "search": "🔬", "terminal": "⚙️"}
    icon = icon_map.get(profile["icon"], "📊")

    st.markdown(f"""
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(244, 208, 63, 0.1);
        border: 1px solid #F4D03F;
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.85em;
    ">
        <span>{icon}</span>
        <span style="color: #F4D03F;">{profile['name']}</span>
    </div>
    """, unsafe_allow_html=True)


def render_profile_switch_button():
    """Render button to switch profiles (in sidebar)."""
    if st.button("Switch Profile", key="switch_profile_btn", use_container_width=True):
        # Clear profile selection to show selector again
        if "teloscope_profile" in st.session_state:
            del st.session_state.teloscope_profile
        if "teloscope_features" in st.session_state:
            del st.session_state.teloscope_features
        st.rerun()
