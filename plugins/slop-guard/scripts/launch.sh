#!/bin/sh

set -u

die() {
    printf '%s\n' "slop-guard plugin: $1" >&2
    exit 1
}

canonicalize_file() {
    target=$1
    links=0

    while [ -L "$target" ]; do
        links=$((links + 1))
        [ "$links" -le 40 ] || return 1
        link=$(command -p readlink "$target" 2>/dev/null) || return 1
        case "$link" in
            /*) target=$link ;;
            *) target=${target%/*}/$link ;;
        esac
    done

    parent=${target%/*}
    name=${target##*/}
    [ "$parent" != "$target" ] || parent=.
    canonical_parent=$(CDPATH= cd -P "$parent" 2>/dev/null && pwd -P) || return 1
    printf '%s/%s\n' "$canonical_parent" "$name"
}

canonicalize_directory() {
    CDPATH= cd -P "$1" 2>/dev/null && pwd -P
}

is_in_git_worktree() {
    directory=${1%/*}

    while :; do
        if [ -e "$directory/.git" ] || [ -L "$directory/.git" ]; then
            return 0
        fi
        [ "$directory" != / ] || return 1
        directory=${directory%/*}
        [ -n "$directory" ] || directory=/
    done
}

trust_target() {
    target=$1

    if is_in_git_worktree "$target"; then
        die "refusing executable from a Git worktree"
    fi

    if [ -n "${VIRTUAL_ENV-}" ]; then
        environment_root=$(canonicalize_directory "$VIRTUAL_ENV") || \
            die "cannot verify active virtual environment"
        [ "$environment_root" != / ] || die "refusing executable from active virtual environment"
        case "$target" in
            "$environment_root"|"$environment_root"/*)
                die "refusing executable from active virtual environment"
                ;;
        esac
    fi
}

resolve_runtime() {
    search_path=${PATH-}
    remaining=$search_path
    found=

    while :; do
        case "$remaining" in
            *:*)
                entry=${remaining%%:*}
                remaining=${remaining#*:}
                more=true
                ;;
            *)
                entry=$remaining
                more=false
                ;;
        esac

        case "$entry" in
            /*)
                candidate=$entry/slop-guard
                if [ -f "$candidate" ] && [ -x "$candidate" ]; then
                    found=$(canonicalize_file "$candidate") || \
                        die "cannot canonicalize installed slop-guard"
                    trust_target "$found"
                    break
                fi
                ;;
            *)
                [ -n "$entry" ] || entry=.
                candidate=$entry/slop-guard
                if [ -f "$candidate" ] && [ -x "$candidate" ]; then
                    die "refusing slop-guard from an empty or relative PATH entry"
                fi
                ;;
        esac

        [ "$more" = true ] || break
    done

    [ -n "$found" ] || die "installed slop-guard not found on absolute PATH entries"
    [ -f "$found" ] && [ -x "$found" ] || die "installed slop-guard is not executable"
    printf '%s\n' "$found"
}

[ "$#" -eq 1 ] || die "expected exactly one operation: mcp or hook"
operation=$1

case "$operation" in
    mcp)
        ;;
    hook)
        case "${CLAUDE_PLUGIN_OPTION_RESPONSE_CHECKS-}" in
            false)
                exit 0
                ;;
            true)
                ;;
            '')
                [ "${PLUGIN_ROOT+x}" = x ] || exit 0
                ;;
            *)
                die "invalid Claude response_checks value"
                ;;
        esac
        ;;
    *)
        die "unknown operation: $operation"
        ;;
esac

runtime=$(resolve_runtime) || exit 1

case "$operation" in
    mcp)
        unset PYTHONHOME PYTHONPATH
        exec "$runtime"
        ;;
    hook)
        hook_path=${runtime%/*}/sg-hook
        [ -f "$hook_path" ] && [ -x "$hook_path" ] || \
            die "installed sg-hook sibling not found"
        hook=$(canonicalize_file "$hook_path") || die "cannot canonicalize installed sg-hook"
        [ "${hook%/*}" = "${runtime%/*}" ] || \
            die "installed sg-hook is not a canonical sibling of slop-guard"
        trust_target "$hook"
        unset PYTHONHOME PYTHONPATH
        exec "$hook"
        ;;
esac
