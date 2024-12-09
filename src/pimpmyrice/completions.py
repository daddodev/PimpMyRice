from __future__ import annotations

import os
import re
import subprocess
import types
from typing import TYPE_CHECKING, Any, Generator, Union

from docopt import (
    Argument,
    Command,
    Either,
    OneOrMore,
    Option,
    Optional,
    Required,
    formal_usage,
    parse_defaults,
    parse_pattern,
    printable_usage,
)

from pimpmyrice.config import HOME_DIR
from pimpmyrice.doc import __doc__ as cli_doc
from pimpmyrice.logger import get_logger

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)

# FROM infi.docopt_completion https://github.com/Infinidat/infi.docopt_completion

# We fill the file template with the command name and the different sections
# generated from the templates below.
# _message_next_arg: outputs the next positional argument name to the user
# with the _message function. It counts the number of elements in the 'words'
# special array that don't begin with '-' (options) and then uses the myargs
# array defined by the caller to output the correct argument name.
# We skip the first two elements in 'words' because the first is always empty and
# the second is the last keyword before the options and arguments start.
FILE_TEMPLATE = '''#compdef {0}

_message_next_arg()
{{
    argcount=0
    for word in "${{words[@][2,-1]}}"
    do
        if [[ $word != -* ]] ; then
            ((argcount++))
        fi
    done
    if [[ $argcount -le ${{#myargs[@]}} ]] ; then
        _message -r $myargs[$argcount]
        if [[ $myargs[$argcount] =~ ".*file.*" || $myargs[$argcount] =~ ".*path.*" ]] ; then
            _files
        fi
    fi
}}
{1}

_{0} "$@"'''

# this is a template of a function called by the completion system when crawling the arguments already
# typed. there is a section for every command and sub-command that the target script supports.
# the variables in the function, "state" and "line" are filled by the _arguments call.
# these variables are handled in "subcommand_switch", which is filled using the SUBCOMMAND_SWITCH_TEMPLATE template
SECTION_TEMPLATE = """
_{cmd_name} ()
{{
    local context state state_descr line
    typeset -A opt_args

    _arguments -C \\
        ':command:->command' \\{opt_list}
        {subcommand_switch}
}}
"""

# if "state" is "command", we call _values which lists the next available options. if state is "options" it means
# that there are more commands typed after the currently handled command, and in that case we use line[1] (the next
# option) to direct the completion system to the next section
# note that the options context is added to the _arguments call here, because this context is only supported when
# there are subcommands
SUBCOMMAND_SWITCH_TEMPLATE = """'*::options:->options'

    case $state in
        (command)
            local -a subcommands
            subcommands=(
{subcommand_list}
            )
            _values '{subcommand}' $subcommands
        ;;

        (options)
            case $line[1] in
{subcommand_cases}
            esac
        ;;
    esac
"""

CASE_TEMPLATE = """                {0})
                    _{1}-{0}
                ;;"""

# When there are positional arguments to the handled context, we use this tempalte.
# We output the name of the next positional argument by using the _message_next_args
# function (defined in FILE_TEMPLATE), unless the current word starts with "-" which means
# the user is trying to type an option (then we specify the available options by using
# _arguments, as in the regular SECTION_TEMPLATE)
ARG_SECTION_TEMPLATE = """
_{cmd_name} ()
{{
    local context state state_descr line
    typeset -A opt_args

    if [[ $words[$CURRENT] == -* ]] ; then
        _arguments -C \\
        ':command:->command' \\{opt_list}

    else
        myargs=({args})
        _message_next_arg
    fi
}}
"""


class CommandParams:
    """Contains command options, arguments, and subcommands.

    Options are optional arguments like "-v", "-h", etc.

    Arguments are required arguments like file paths, etc.

    Subcommands are optional keywords, like the "status" in "git status".
    Subcommands have their own CommandParams instance, so the "status" in "git status" can
    have its own options, arguments, and subcommands.

    This way, we can describe commands like "git remote add origin --fetch" with all the different
    options at each level.
    """

    def __init__(self) -> None:
        self.arguments: list[str] = []
        self.options: list[str] = []
        self.subcommands: dict[str, "CommandParams"] = {}

    def get_subcommand(self, subcommand: str) -> "CommandParams":
        return self.subcommands.setdefault(subcommand, CommandParams())

    def repr(self, indent: int) -> str:
        s = " " * indent + "cmds:\n"
        for cmd in self.subcommands:
            s += (
                " " * (indent + 4)
                + f"{cmd}:\n{self.subcommands[cmd].repr(indent + 5 + len(cmd))}\n"
            )
        s += " " * indent + f"args: {self.arguments}\n"
        s += " " * indent + f"opts: {self.options}\n"
        return s

    def __repr__(self) -> str:
        return self.repr(0)


class DocoptCompletionException(Exception):
    """Custom exception for docopt completion errors."""

    pass


def build_command_tree(pattern: Any, cmd_params: "CommandParams") -> "CommandParams":
    """
    Recursively fill in a command tree in cmd_params according to a docopt-parsed "pattern" object.
    """
    if type(pattern) in [Either, Optional, OneOrMore]:
        for child in pattern.children:
            build_command_tree(child, cmd_params)
    elif type(pattern) in [Required]:
        for child in pattern.children:
            cmd_params = build_command_tree(child, cmd_params)
    elif type(pattern) in [Option]:
        suffix = "=" if pattern.argcount else ""
        if pattern.short:
            cmd_params.options.append(pattern.short + suffix)
        if pattern.long:
            cmd_params.options.append(pattern.long + suffix)
    elif type(pattern) in [Command]:
        cmd_params = cmd_params.get_subcommand(pattern.name)
    elif type(pattern) in [Argument]:
        cmd_params.arguments.append(pattern.name)
    return cmd_params


def get_usage(cmd: str) -> str:
    """
    Runs a command with --help and extracts its usage description.

    :param cmd: Command to execute.
    :return: Usage string extracted from the command's help output.
    :raises: DocoptCompletionException if the command execution fails or returns an error code.
    """
    error_message = f"Failed to run '{cmd} --help'"
    try:
        cmd_process = subprocess.Popen(
            [cmd, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError:
        raise DocoptCompletionException(f"{error_message} : command does not exist")
    usage = bytes()
    while True:
        nextline = cmd_process.stdout.readline()  # type: ignore
        if len(nextline) == 0 and cmd_process.poll() is not None:
            break
        usage += nextline
    if cmd_process.returncode != 0:
        raise DocoptCompletionException(
            f"{error_message} : command returned {cmd_process.returncode}"
        )
    return usage.decode("ascii")


def get_options_descriptions(doc: str) -> Generator[tuple[str, str], None, None]:
    """
    Extracts option descriptions from the docopt documentation string.

    :param doc: Documentation string from which to parse options.
    :return: A generator yielding tuples of (option, description).
    """

    def sanitize_line(line: str) -> str:
        return (
            line.replace("'", "'\\''").replace("[", "\\[").replace("]", "\\]").strip()
        )

    for arg in re.findall("\n  .*", doc):
        options, partition, description = arg.strip().partition("  ")
        if not partition:
            continue
        if not options.startswith("-"):
            yield options, sanitize_line(description)
            continue
        options = options.replace(",", " ")
        options = re.sub(r"=\S+", "= ", options)
        for s in options.split():
            yield s, sanitize_line(description)


def parse_params(cmd: str) -> tuple["CommandParams", dict[str, str]]:
    """
    Creates a parameter tree (CommandParams object) for the target docopt tool.
    Also parses a mapping of options to their help descriptions.

    :param cmd: The command to parse.
    :return: A tuple containing the CommandParams object and a dictionary of option descriptions.
    """
    usage = get_usage(cmd)
    options = parse_defaults(usage)
    pattern = parse_pattern(formal_usage(printable_usage(usage)), options)
    param_tree = CommandParams()
    build_command_tree(pattern, param_tree)
    return param_tree, dict(get_options_descriptions(usage))


class CompletionGenerator:
    """Completion file generator base class."""

    def _write_to_file(self, file_path: str, completion_file_content: str) -> None:
        if not os.access(os.path.dirname(file_path), os.W_OK):
            print(
                "Skipping file {file_path}, no permissions".format(file_path=file_path)
            )
            return
        try:
            with open(file_path, "w") as fd:
                fd.write(completion_file_content)
        except IOError:
            print("Failed to write {file_path}".format(file_path=file_path))
            return
        print("Completion file written to {file_path}".format(file_path=file_path))

    def get_name(self) -> str:
        raise NotImplementedError()

    def get_completion_path(self) -> str:
        raise NotImplementedError()

    def get_completion_filepath(
        self, cmd: str
    ) -> Union[str, Generator[str, None, None]]:
        raise NotImplementedError()

    def get_completion_file_content(
        self, cmd: str, param_tree: Any, option_help: dict[str, str]
    ) -> str:
        raise NotImplementedError()

    def completion_path_exists(self) -> bool:
        return os.path.exists(self.get_completion_path())

    def generate(self, cmd: str, param_tree: Any, option_help: dict[str, str]) -> None:
        completion_file_content = self.get_completion_file_content(
            cmd, param_tree, option_help
        )
        file_paths = self.get_completion_filepath(cmd)
        if not isinstance(file_paths, types.GeneratorType):
            file_paths = [file_paths]  # type: ignore
        for file_path in file_paths:
            self._write_to_file(file_path, completion_file_content)


class ZshCompletion(CompletionGenerator):
    """Base class for generating ZSH completion files"""

    def get_completion_path(self) -> str:
        return "."

    def get_completion_filepath(self, cmd: str) -> str:
        return os.path.join(self.get_completion_path(), f"_{cmd}")

    def create_opt_menu(self, opts: list[str], option_help: dict[str, str]) -> str:
        if not opts:
            return ""
        show_help = all(opt in option_help for opt in opts)

        def get_option_help(opt: str) -> str:
            if not show_help or opt not in option_help:
                return ""
            return f"[{option_help[opt]}]"

        def decorate_opt(opt: str) -> str:
            return (opt + "-") if opt.endswith("=") else opt

        return "\n" + "\n".join(
            [
                f"\t\t'({decorate_opt(opt)}){decorate_opt(opt)}{get_option_help(opt)}' \\"
                for opt in opts
            ]
        )

    def create_subcommand_cases(self, cmd_name: str, subcmds: list[str]) -> str:
        return "\n".join([CASE_TEMPLATE.format(cmd, cmd_name) for cmd in subcmds])

    def create_subcommand_list(
        self, cmd_name: str, option_help: dict[str, str], subcmds: list[str]
    ) -> str:
        def get_subcmd_help(subcmd: str) -> Optional[str]:
            for i in [0, 1]:
                subcommand_with_trail = " ".join(
                    cmd_name.replace("-", " ").split()[i:] + [subcmd]
                )
                if subcommand_with_trail in option_help:
                    return option_help[subcommand_with_trail]
            return None

        show_help = all(get_subcmd_help(subcmd) is not None for subcmd in subcmds)

        def get_help_opt(subcmd: str) -> str:
            if not show_help:
                return ""
            return f"[{get_subcmd_help(subcmd)}]"

        return "\n".join(
            [f"\t\t\t\t'{subcmd}{get_help_opt(subcmd)}'" for subcmd in subcmds]
        )

    def create_subcommand_switch(
        self, cmd_name: str, option_help: dict[str, str], subcommands: dict[str, Any]
    ) -> str:
        if len(subcommands) == 0:
            return ""
        subcommand_list = self.create_subcommand_list(
            cmd_name, option_help, list(subcommands.keys())
        )
        subcommand_cases = self.create_subcommand_cases(
            cmd_name, list(subcommands.keys())
        )
        return SUBCOMMAND_SWITCH_TEMPLATE.format(
            subcommand_list=subcommand_list,
            subcommand_cases=subcommand_cases,
            subcommand=cmd_name.replace("-", " "),
        )

    def create_args_section(self, cmd_name: str, opt_list: str, args: list[str]) -> str:
        return ARG_SECTION_TEMPLATE.format(
            cmd_name=f"{cmd_name}",
            args=" ".join(f"'{arg}'" for arg in args),
            opt_list=opt_list,
        )

    def create_section(
        self, cmd_name: str, param_tree: Any, option_help: dict[str, str]
    ) -> str:
        subcommands = param_tree.subcommands
        opts = param_tree.options
        args = param_tree.arguments
        opt_list = self.create_opt_menu(opts, option_help)
        if args:
            return self.create_args_section(cmd_name, opt_list, args)
        subcommand_switch = self.create_subcommand_switch(
            cmd_name, option_help, subcommands
        )
        res = SECTION_TEMPLATE.format(
            cmd_name=cmd_name, opt_list=opt_list, subcommand_switch=subcommand_switch
        )
        for subcommand_name, subcommand_tree in subcommands.items():
            res += self.create_section(
                f"{cmd_name}-{subcommand_name}", subcommand_tree, option_help
            )
        return res

    def get_completion_file_content(
        self, cmd: str, param_tree: Any, option_help: dict[str, str]
    ) -> str:
        completion_file_inner_content = self.create_section(
            cmd, param_tree, option_help
        )
        return FILE_TEMPLATE.format(cmd, completion_file_inner_content)


class OhMyZshCompletion(ZshCompletion):
    def get_name(self) -> str:
        return "ZSH with oh-my-zsh"

    def get_completion_path(self) -> str:
        return os.path.expanduser("~/.oh-my-zsh")

    def get_completion_filepath(self, cmd: str) -> str:
        completion_path = os.path.expanduser("~/.oh-my-zsh/completions")
        if not os.path.exists(completion_path):
            os.makedirs(completion_path)
        return os.path.join(completion_path, f"_{cmd}")


# END FROM infi.docopt_completion


def add_zsh_suggestions(file_content: str, arg_name: str, values: list[str]) -> str:
    if arg_name == "--tags":
        replaced = ""

        found_tags = False
        for i, line in enumerate(file_content.splitlines()):
            if "(--tags=-)--tags=-" in line:
                found_tags = True
                line = "		'--tags=:flag:->flags' \\"
            elif "}" in line and found_tags:
                found_tags = False
                line = f"""
    case "$state" in flags)
        _values -s , 'flags' {" ".join(f'"{x}"' for x in values)}
    esac
}}
"""

            replaced += line + "\n"

    elif arg_name == "IMAGE":

        replaced = file_content.replace(
            f"""
        myargs=('{arg_name.upper()}')
        _message_next_arg
""",
            f"""
        myargs=('{arg_name.upper()}')
        _files
""",
        )
    else:

        replaced = file_content.replace(
            f"""
        myargs=('{arg_name.upper()}')
        _message_next_arg
""",
            f"""
        local -a available_{arg_name}s
        available_{arg_name}s=({" ".join(f'"{x}"' for x in values)})

        _describe '{arg_name} name' available_{arg_name}s
""",
        )

    return replaced


def generate_shell_suggestions(tm: ThemeManager) -> None:
    file_path = HOME_DIR / ".cache/oh-my-zsh/completions/_pimp"

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # TODO fork docopt_completion

    doc = cli_doc

    options = parse_defaults(doc)
    pattern = parse_pattern(formal_usage(printable_usage(doc)), options)
    param_tree = CommandParams()
    build_command_tree(pattern, param_tree)
    option_help = dict(list(get_options_descriptions(doc)))

    generator = ZshCompletion()

    content = generator.get_completion_file_content("pimp", param_tree, option_help)

    content = add_zsh_suggestions(content, "theme", [*tm.themes.keys()])
    content = add_zsh_suggestions(content, "module", [*tm.mm.modules.keys()])
    content = add_zsh_suggestions(content, "--tags", list(tm.tags))
    content = add_zsh_suggestions(content, "IMAGE", [])

    try:
        with open(file_path, "w") as fd:
            fd.write(content)
    except IOError:
        log.debug("Failed to write {file_path}".format(file_path=file_path))
        return
    log.debug("Completion file written to {file_path}".format(file_path=file_path))
