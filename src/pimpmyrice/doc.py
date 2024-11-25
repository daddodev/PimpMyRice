"""
See https://pimpmyrice.vercel.app/docs for more info.

Usage:
    pimp gen IMAGE...       [--apply] [--name=NAME] [--tags=TAGS] [--style=STYLE]
                            [--palette=PALETTE] [options]
    pimp random             [--mode=MODE] [--name=NAME] [--tags=TAGS]
                            [--exclude-tags=TAGS] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp refresh            [--mode=MODE] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set theme THEME    [--mode=MODE] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set mode MODE [options]
    pimp delete theme THEME [options]
    pimp rename theme THEME NEW_NAME [options]
    pimp toggle mode [options]
    pimp clone module MODULE_URL [options]
    pimp delete module MODULE [options]
    pimp run module MODULE COMMAND [COMMAND_ARGS...] [options]
    pimp list (themes|tags|styles|palettes|keywords|modules) [options]
    pimp edit theme [THEME] [options]
    pimp edit style STYLE [options]
    pimp edit palette PALETTE [options]
    pimp edit keywords [options]
    pimp edit module MODULE [options]
    pimp regen [--name=NAME] [options]
    pimp rewrite [--name=NAME] [options]
    pimp info [options]
    pimp --help

Options:
    --verbose, -v
"""
