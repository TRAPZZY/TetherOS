"""register.py -- central registry for all command modules"""

def register_all(commands, aliases):
    from app.commands.recon import register as reg_recon
    from app.commands.exploit import register as reg_exploit
    from app.commands.anon import register as reg_anon
    from app.commands.scan import register as reg_scan
    from app.commands.web import register as reg_web
    from app.commands.forensics import register as reg_forensics
    from app.commands.cron import register as reg_cron
    from app.commands.wireless import register as reg_wireless
    reg_recon(commands, aliases)
    reg_exploit(commands, aliases)
    reg_anon(commands, aliases)
    reg_scan(commands, aliases)
    reg_web(commands, aliases)
    reg_forensics(commands, aliases)
    reg_cron(commands, aliases)
    reg_wireless(commands, aliases)
    return commands, aliases
