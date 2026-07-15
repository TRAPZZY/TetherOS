"""commands -- Tether OS command modules"""

def register_all(cmds, aliases):
    from app.commands.register import register_all as _ra
    return _ra(cmds, aliases)
