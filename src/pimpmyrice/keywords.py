default_base_style = {
    "bar": {"bg": "$panel.bg", "fg": "$panel.fg"},
    "blur": {"enabled": True, "passes": 3, "strength": 7},
    "border": {"radius": 0, "width": 3},
    "font": {
        "normal": {"family": "sans-serif", "size": 12},
        "mono": {"family": "monospace", "size": 10},
    },
    "gaps": {"inner": 10, "outer": 20},
    "opacity": {"active": 0.98, "inactive": 0.95, "terminal": 0.97},
    "padding": {"x": 10, "y": 10},
    "shadow": {"enabled": True, "offset": 10, "opacity": 0.4, "blur": 10, "spread": 10},
    "titlebar": {
        "enabled": True,
        "active": {"bg": "$border.active", "fg": "$primary.fg"},
        "inactive": {"bg": "$border.inactive", "fg": "$normal.fg"},
    },
    "animations": {"enabled": True, "speed": 2, "style": "default"},
    "cursor": {"name": "Adwaita", "size": 24},
    "modules_styles": {},
}
