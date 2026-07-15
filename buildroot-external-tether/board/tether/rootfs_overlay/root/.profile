# Auto-launch Tether OS shell on login
if [ -z "$TETHER_ACTIVE" ] && [ -x /usr/bin/tether ]; then
    export TETHER_ACTIVE=1
    cd /home/tether
    /usr/bin/tether
fi
