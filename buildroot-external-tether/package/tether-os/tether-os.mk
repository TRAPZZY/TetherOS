TETHER_OS_VERSION = 2.0.0rc1
TETHER_OS_SITE_METHOD = local
TETHER_OS_SITE = $(realpath $(BR2_EXTERNAL_TETHER_OS_PATH)/..)

define TETHER_OS_INSTALL_TARGET_CMDS
    mkdir -p $(TARGET_DIR)/usr/lib/tether-os
    cp -r $(@D)/app $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/kernel $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/lib $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/wordlists $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/etc $(TARGET_DIR)/usr/lib/tether-os/
    cp $(@D)/setup.py $(TARGET_DIR)/usr/lib/tether-os/
    cp $(@D)/etc/tether.conf $(TARGET_DIR)/etc/tether.conf
    printf '%s\n' '#!/bin/sh' \
        'export PYTHONPATH=/usr/lib/tether-os$${PYTHONPATH:+:$${PYTHONPATH}}' \
        'cd /usr/lib/tether-os' \
        'exec python3 -m app.entrypoint "$$@"' \
        > $(TARGET_DIR)/usr/bin/tether
    chmod +x $(TARGET_DIR)/usr/bin/tether
endef

$(eval $(generic-package))
