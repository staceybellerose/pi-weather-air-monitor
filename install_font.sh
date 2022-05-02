#!/bin/bash

if [[ $EUID -ne 0 ]]; then
    echo "$0 is not running as root. Try using sudo."
    exit 2
fi

mkdir -p /usr/share/fonts/truetype/meteocons
cp meteocons.ttf /usr/share/fonts/truetype/meteocons/
fc-cache -f -v
