"""Shell completion scripts for bash, zsh, and fish."""

from __future__ import annotations

COMMANDS = [
    "list", "ls", "show", "info", "disk", "du", "pressure", "mem",
    "bench", "watch", "top", "serve", "hw", "suggest", "updates",
    "cleanup", "config",
]

GLOBAL_FLAGS = ["--json", "--host", "--no-pager", "--help", "--version"]

CAPABILITIES = ["vision", "thinking", "tools", "embedding", "completion"]

TASKS = ["general", "coding", "math", "vision", "chat", "embedding", "thinking", "tools"]


def bash_completion() -> str:
    cmds = " ".join(COMMANDS)
    flags = " ".join(GLOBAL_FLAGS)
    caps = " ".join(CAPABILITIES)
    tasks = " ".join(TASKS)

    return f"""\
# omon bash completion
# Add to ~/.bashrc: eval "$(omon completions bash)"

_omon_completions() {{
    local cur prev commands
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    commands="{cmds}"

    # Complete command names
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=($(compgen -W "${{commands}} {flags}" -- "${{cur}}"))
        return
    fi

    # Context-sensitive completions
    case "${{prev}}" in
        --cap)
            COMPREPLY=($(compgen -W "{caps}" -- "${{cur}}"))
            return ;;
        --task)
            COMPREPLY=($(compgen -W "{tasks}" -- "${{cur}}"))
            return ;;
        --host|--port|--days|--compare)
            return ;;
        show|info)
            # Complete with installed model names
            local models
            models=$(omon list --json 2>/dev/null | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)]" 2>/dev/null)
            COMPREPLY=($(compgen -W "${{models}}" -- "${{cur}}"))
            return ;;
        bench)
            local models
            models=$(omon list --json 2>/dev/null | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)]" 2>/dev/null)
            COMPREPLY=($(compgen -W "${{models}}" -- "${{cur}}"))
            return ;;
    esac

    # Global flags for any subcommand
    COMPREPLY=($(compgen -W "{flags}" -- "${{cur}}"))
}}

complete -F _omon_completions omon
"""


def zsh_completion() -> str:
    cmds_desc = "\n        ".join(
        f"'{c}:omon {c}'" for c in COMMANDS
    )
    caps = " ".join(CAPABILITIES)
    tasks = " ".join(TASKS)

    return f"""\
#compdef omon
# omon zsh completion
# Add to ~/.zshrc: eval "$(omon completions zsh)"

_omon() {{
    local -a commands
    commands=(
        {cmds_desc}
    )

    _arguments -C \\
        '--json[Output as JSON]' \\
        '--host[Ollama host]:host:' \\
        '--no-pager[Disable auto-paging]' \\
        '--version[Show version]' \\
        '--help[Show help]' \\
        '1:command:->command' \\
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[1] in
                show|info|bench)
                    local -a models
                    models=(${{(f)"$(omon list --json 2>/dev/null | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)]" 2>/dev/null)"}})
                    _describe 'model' models
                    ;;
                list|ls)
                    _arguments '--cap[Filter by capability]:capability:({caps})'
                    ;;
                suggest)
                    _arguments '--task[Task type]:task:({tasks})'
                    ;;
                serve)
                    _arguments '--port[Port number]:port:'
                    ;;
                cleanup)
                    _arguments '--days[Stale threshold]:days:'
                    ;;
                config)
                    _arguments '--init[Create default config]'
                    ;;
            esac
            ;;
    esac
}}

_omon "$@"
"""


def fish_completion() -> str:
    caps = " ".join(CAPABILITIES)
    tasks = " ".join(TASKS)

    lines = [
        "# omon fish completion",
        '# Add to fish: omon completions fish | source',
        "",
        "# Disable file completions",
        "complete -c omon -f",
        "",
        "# Global flags",
        "complete -c omon -l json -d 'Output as JSON'",
        "complete -c omon -l host -x -d 'Ollama host'",
        "complete -c omon -l no-pager -d 'Disable auto-paging'",
        "complete -c omon -l version -d 'Show version'",
        "",
        "# Commands",
    ]

    cmd_help = {
        "list": "List installed models", "ls": "List installed models",
        "show": "Show model details", "info": "Show model details",
        "disk": "Disk usage", "du": "Disk usage",
        "pressure": "Memory pressure", "mem": "Memory pressure",
        "bench": "Benchmark a model", "watch": "Live TUI", "top": "Live TUI",
        "serve": "Web dashboard", "hw": "Hardware profile",
        "suggest": "Suggest models", "updates": "Check updates",
        "cleanup": "Cleanup suggestions", "config": "Configuration",
    }

    for cmd, desc in cmd_help.items():
        lines.append(f"complete -c omon -n '__fish_use_subcommand' -a '{cmd}' -d '{desc}'")

    lines.extend([
        "",
        "# Subcommand-specific flags",
        f"complete -c omon -n '__fish_seen_subcommand_from list ls' -l cap -x -a '{caps}' -d 'Filter by capability'",
        f"complete -c omon -n '__fish_seen_subcommand_from suggest' -l task -x -a '{tasks}' -d 'Task type'",
        "complete -c omon -n '__fish_seen_subcommand_from serve' -l port -x -d 'Port number'",
        "complete -c omon -n '__fish_seen_subcommand_from cleanup' -l days -x -d 'Stale threshold'",
        "complete -c omon -n '__fish_seen_subcommand_from config' -l init -d 'Create default config'",
        "",
        "# Model name completion for show/bench",
        "complete -c omon -n '__fish_seen_subcommand_from show info bench' -a '(omon list --json 2>/dev/null | python3 -c \"import sys,json; [print(m[\\'name\\']) for m in json.load(sys.stdin)]\" 2>/dev/null)'",
    ])

    return "\n".join(lines) + "\n"
