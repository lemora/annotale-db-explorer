BLUE_DARK_BORDER = "#35546a"
BLUE_DARK_BG_TOP = "#132531"
BLUE_DARK_BG_BOTTOM = "#1a3444"
BLUE_DARK_ACCENT = "#aac4d8"
BLUE_DARK_TITLE = "#eef6fb"
BLUE_DARK_LABEL = "#d7e9f5"
BLUE_DARK_TEXT = "#dceaf3"
BLUE_DARK_CHIP_BG = "#274457"
BLUE_DARK_CHIP_TEXT = "#e8f3fa"
PSEUDO_TALE_GREY = "#6b7280"
SELECTED_ACCENT = "#ff7f0e"


def blue_card_dark_mode_css(
    *,
    card_selector: str,
    title_selector: str,
    sub_selector: str,
    label_selector: str,
    text_selector: str,
    chip_selector: str | None = None,
    link_card_selector: str | None = None,
    link_title_selector: str | None = None,
    link_text_selector: str | None = None,
) -> str:
    parts = [
        "@media (prefers-color-scheme: dark) {",
        f"    {card_selector} {{",
        f"        border-color: {BLUE_DARK_BORDER};",
        f"        background: linear-gradient(180deg, {BLUE_DARK_BG_TOP} 0%, {BLUE_DARK_BG_BOTTOM} 100%);",
        "    }",
        f"    {title_selector} {{",
        f"        color: {BLUE_DARK_TITLE};",
        "    }",
        f"    {sub_selector} {{",
        f"        color: {BLUE_DARK_ACCENT};",
        "    }",
        f"    {label_selector} {{",
        f"        color: {BLUE_DARK_LABEL};",
        "    }",
        f"    {text_selector} {{",
        f"        color: {BLUE_DARK_TEXT};",
        "    }",
    ]

    if chip_selector is not None:
        parts.extend(
            [
                f"    {chip_selector} {{",
                f"        background: {BLUE_DARK_CHIP_BG};",
                f"        color: {BLUE_DARK_CHIP_TEXT};",
                "    }",
            ]
        )

    if link_card_selector is not None:
        parts.extend(
            [
                f"    {link_card_selector} {{",
                f"        border-color: {BLUE_DARK_BORDER};",
                f"        background: {BLUE_DARK_BG_TOP};",
                "    }",
            ]
        )

    if link_title_selector is not None:
        parts.extend(
            [
                f"    {link_title_selector} {{",
                f"        color: {BLUE_DARK_TITLE};",
                "    }",
            ]
        )

    if link_text_selector is not None:
        parts.extend(
            [
                f"    {link_text_selector} {{",
                f"        color: {BLUE_DARK_ACCENT};",
                "    }",
            ]
        )

    parts.append("}")
    return "\n".join(parts)
