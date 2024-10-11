base_style = {
    "bar": {"bg": "$panel.bg", "fg": "$panel.fg", "split": False},
    "blur": {"enabled": True, "passes": 3, "strength": 7},
    "border": {"radius": 15, "width": 3},
    "font": {
        "mono": "Bitstream Vera Sans Mono",
        "normal": "Bitstream Vera Sans",
        "size": 10,
    },
    "gaps": {"inner": 10, "outer": 10},
    "opacity": {"active": 0.98, "inactive": 0.95, "terminal": 0.97},
    "padding": {"h": 10, "v": 10},
    "shadow": {"enabled": True, "offset": 15, "opacity": 0.55, "radius": 0},
    "titlebar": {
        "active": {"bg": "$border.active", "fg": "$primary.fg"},
        "inactive": {"bg": "$border.inactive", "fg": "$primary.fg"},
    },
    "animations": {"enabled": True},
}
