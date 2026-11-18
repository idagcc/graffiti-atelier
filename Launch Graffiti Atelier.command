#!/bin/zsh
app_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
open -a TouchDesigner "$app_dir/Graffiti Atelier.toe"
