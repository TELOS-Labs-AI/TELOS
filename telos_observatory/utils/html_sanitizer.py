"""
HTML Sanitization Utilities for TELOS Observatory
==================================================

Provides functions to sanitize user input before rendering with
unsafe_allow_html=True in Streamlit components.

This prevents XSS (Cross-Site Scripting) attacks by escaping or
removing potentially dangerous HTML content.

Usage:
    from telos_observatory.utils.html_sanitizer import sanitize_html, escape_html, sanitize_for_display

    # Escape all HTML (safest)
    safe_text = escape_html(user_input)

    # Allow basic formatting (bold, italic, etc.)
    safe_html = sanitize_html(user_input)

    # For displaying in chat/message contexts
    safe_display = sanitize_for_display(user_input)
"""

import html
import re
from typing import Optional, List, Set


# Tags that are considered safe for basic formatting
SAFE_TAGS: Set[str] = {
    'b', 'strong', 'i', 'em', 'u', 'code', 'pre', 'br',
    'p', 'span', 'div', 'ul', 'ol', 'li', 'blockquote'
}

# Attributes that are considered safe (subset of standard attributes)
SAFE_ATTRIBUTES: Set[str] = {
    'class', 'id', 'style'
}

# Dangerous patterns to always remove
DANGEROUS_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<embed[^>]*>', re.IGNORECASE),
    re.compile(r'<link[^>]*>', re.IGNORECASE),
    re.compile(r'<meta[^>]*>', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick, onload, onerror, etc.
    re.compile(r'data:', re.IGNORECASE),
    re.compile(r'vbscript:', re.IGNORECASE),
]

# Style properties that could be dangerous
DANGEROUS_STYLE_PATTERNS = [
    re.compile(r'expression\s*\(', re.IGNORECASE),
    re.compile(r'url\s*\([^)]*javascript', re.IGNORECASE),
    re.compile(r'behavior\s*:', re.IGNORECASE),
    re.compile(r'-moz-binding', re.IGNORECASE),
]


def escape_html(text: str) -> str:
    """
    Escape all HTML characters in text.

    This is the safest option - converts all < > & " ' to HTML entities.
    Use this when you don't need any HTML formatting at all.

    Args:
        text: The input text to escape

    Returns:
        Text with all HTML characters escaped
    """
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def remove_dangerous_patterns(text: str) -> str:
    """
    Remove known dangerous patterns from text.

    Args:
        text: The input text

    Returns:
        Text with dangerous patterns removed
    """
    if not text:
        return ""

    result = text
    for pattern in DANGEROUS_PATTERNS:
        result = pattern.sub('', result)

    return result


def sanitize_style(style: str) -> str:
    """
    Sanitize CSS style attribute value.

    Args:
        style: The style attribute value

    Returns:
        Sanitized style string
    """
    if not style:
        return ""

    for pattern in DANGEROUS_STYLE_PATTERNS:
        if pattern.search(style):
            return ""  # Remove entire style if dangerous

    return style


def sanitize_html(
    text: str,
    allowed_tags: Optional[Set[str]] = None,
    allowed_attributes: Optional[Set[str]] = None
) -> str:
    """
    Sanitize HTML by allowing only safe tags and removing dangerous content.

    This provides a balance between allowing formatting and security.

    Args:
        text: The input HTML text
        allowed_tags: Set of allowed tag names (defaults to SAFE_TAGS)
        allowed_attributes: Set of allowed attributes (defaults to SAFE_ATTRIBUTES)

    Returns:
        Sanitized HTML string
    """
    if not text:
        return ""

    allowed_tags = allowed_tags or SAFE_TAGS
    allowed_attributes = allowed_attributes or SAFE_ATTRIBUTES

    # First, remove known dangerous patterns
    result = remove_dangerous_patterns(text)

    # Parse and rebuild HTML allowing only safe elements
    # Simple regex-based approach (for production, consider bleach or lxml)
    tag_pattern = re.compile(r'<(/?)(\w+)([^>]*)>', re.IGNORECASE)

    def replace_tag(match):
        closing = match.group(1)
        tag_name = match.group(2).lower()
        attributes = match.group(3)

        if tag_name not in allowed_tags:
            return ''  # Remove disallowed tags

        # For allowed tags, filter attributes
        if attributes and not closing:
            safe_attrs = []
            attr_pattern = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')

            for attr_match in attr_pattern.finditer(attributes):
                attr_name = attr_match.group(1).lower()
                attr_value = attr_match.group(2)

                if attr_name in allowed_attributes:
                    if attr_name == 'style':
                        attr_value = sanitize_style(attr_value)
                        if attr_value:
                            safe_attrs.append(f'{attr_name}="{attr_value}"')
                    else:
                        # Escape attribute value
                        safe_value = html.escape(attr_value, quote=True)
                        safe_attrs.append(f'{attr_name}="{safe_value}"')

            if safe_attrs:
                return f'<{closing}{tag_name} {" ".join(safe_attrs)}>'

        return f'<{closing}{tag_name}>'

    result = tag_pattern.sub(replace_tag, result)

    return result


def sanitize_for_display(
    text: str,
    preserve_newlines: bool = True,
    max_length: Optional[int] = None
) -> str:
    """
    Sanitize text for display in chat/message contexts.

    Escapes HTML but preserves line breaks and optionally truncates.

    Args:
        text: The input text
        preserve_newlines: Convert newlines to <br> tags
        max_length: Maximum length (truncates with ... if exceeded)

    Returns:
        Sanitized text safe for HTML display
    """
    if not text:
        return ""

    result = str(text)

    # Truncate if needed (before escaping)
    if max_length and len(result) > max_length:
        result = result[:max_length - 3] + "..."

    # Escape HTML
    result = escape_html(result)

    # Convert newlines to <br> if requested
    if preserve_newlines:
        result = result.replace('\n', '<br>')

    return result


def sanitize_markdown(text: str) -> str:
    """
    Sanitize text that will be rendered as Markdown.

    Removes potential XSS vectors that could be embedded in Markdown.

    Args:
        text: The Markdown text

    Returns:
        Sanitized Markdown text
    """
    if not text:
        return ""

    result = text

    # Remove dangerous patterns
    result = remove_dangerous_patterns(result)

    # Remove raw HTML tags (Markdown should use markdown syntax)
    result = re.sub(r'<[^>]+>', '', result)

    return result


def create_safe_html_element(
    tag: str,
    content: str,
    attributes: Optional[dict] = None,
    escape_content: bool = True
) -> str:
    """
    Create an HTML element with properly escaped content.

    Args:
        tag: The HTML tag name
        content: The content inside the tag
        attributes: Optional dict of attributes
        escape_content: Whether to escape the content (default True)

    Returns:
        Safe HTML string
    """
    if tag.lower() not in SAFE_TAGS:
        raise ValueError(f"Tag '{tag}' is not in the safe list")

    safe_content = escape_html(content) if escape_content else content

    if attributes:
        attr_str = ' '.join(
            f'{k}="{escape_html(str(v))}"'
            for k, v in attributes.items()
            if k.lower() in SAFE_ATTRIBUTES
        )
        return f'<{tag} {attr_str}>{safe_content}</{tag}>'

    return f'<{tag}>{safe_content}</{tag}>'
