TETHER_OS_VERSION = 1.0.0
TETHER_OS_SITE_METHOD = local
TETHER_OS_SITE = $(BR2_EXTERNAL_TETHER_OS_PATH)/../

define TETHER_OS_INSTALL_TARGET_CMDS
    mkdir -p $(TARGET_DIR)/usr/lib/tether-os
    cp -r $(@D)/app $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/kernel $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/lib $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/wordlists $(TARGET_DIR)/usr/lib/tether-os/
    cp -r $(@D)/etc $(TARGET_DIR)/usr/lib/tether-os/
    cp $(@D)/setup.py $(TARGET_DIR)/usr/lib/tether-os/
    ln -sf /usr/lib/tether-os/app/shell.py $(TARGET_DIR)/usr/bin/tether
    chmod +x $(TARGET_DIR)/usr/bin/tether
endef

$(eval $(generic-package))
