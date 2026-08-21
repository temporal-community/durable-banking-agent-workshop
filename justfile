default:
    @just --list

create:
    #!/usr/bin/env bash
    set -euo pipefail
    slug=$(grep -E '^slug:' instruqt/track.yml | head -1 | awk '{print $2}' | tr -d '"')
    title=$(grep -E '^title:' instruqt/track.yml | head -1 | sed -E 's/^title:[[:space:]]*//' | sed -E 's/^"(.*)"$/\1/')
    tmp=$(mktemp -d)
    (cd "$tmp" && instruqt track create "$slug" --title "$title")
    rm -rf "$tmp"
    echo "Registered slug '$slug' (maintenance mode). Next: 'just init'."

init:
    cd instruqt && instruqt track push --force
    @echo ""
    @echo "instruqt/track.yml now has an assigned 'id:'. Commit it:"
    @echo "    git add instruqt/ && git commit -S -m 'Pin Instruqt track and tab ids'"

push:
    cd instruqt && instruqt track push

pull:
    cd instruqt && instruqt track pull

validate:
    cd instruqt && instruqt track validate

test:
    cd instruqt && instruqt track test

clean-remote:
    find instruqt/ -name "*.remote" -delete
