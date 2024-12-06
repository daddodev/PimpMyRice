"""
See https://pimpmyrice.vercel.app/docs for more info.

Usage:
    pimp gen IMAGE...       [--apply] [--name=NAME] [--tags=TAGS] [options]
    pimp random             [--mode=MODE] [--name=NAME] [--tags=TAGS]
                            [--exclude-tags=TAGS] [--modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp refresh            [--mode=MODE] [--modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set theme THEME    [--mode=MODE] [--modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set mode MODE [options]
    pimp delete theme THEME [options]
    pimp rename theme THEME NEW_NAME [options]
    pimp toggle mode [options]
    pimp add tags THEMES... --tags=TAGS
    pimp remove tags [THEMES...] --tags=TAGS
    pimp clone module MODULE_URL... [options]
    pimp delete module MODULE [options]
    pimp reinit module MODULE [options]
    pimp run module MODULE COMMAND [COMMAND_ARGS...] [options]
    pimp list (themes|tags|styles|palettes|keywords|modules) [options]
    pimp edit theme [THEME] [options]
    pimp edit base-style [options]
    pimp edit style STYLE [options]
    pimp edit palette PALETTE [options]
    pimp edit module MODULE [options]
    pimp regen [--name=NAME] [options]
    pimp rewrite (themes|modules) [--name=NAME] [options]
    pimp export theme THEME OUT_DIR     [--mode=MODE] [--modules=MODULES]
                                        [--exclude-modules=MODULES] [--style=STYLE]
                                        [--palette=PALETTE] [--print-theme-dict]
                                        [options]
    pimp info [options]
    pimp --help

Options:
    --verbose, -v
"""
