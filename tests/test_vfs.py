from app.vfs import VirtualFS


def test_standard_tree_is_reachable_from_root():
    vfs = VirtualFS()
    assert {"etc", "home", "proc", "tmp"}.issubset(set(vfs.listdir("/")))
    assert "net" in vfs.listdir("/proc")


def test_recursive_create_move_and_restore():
    vfs = VirtualFS()
    assert vfs.makedirs("/tmp/a/b")
    assert vfs.write("/tmp/a/b/data.txt", "payload")
    assert vfs.rename("/tmp/a", "/tmp/moved")
    assert vfs.read("/tmp/moved/b/data.txt") == "payload"

    restored = VirtualFS()
    assert restored.load_dict(vfs.to_dict())
    assert restored.read("/tmp/moved/b/data.txt") == "payload"


def test_find_supports_shell_patterns_and_du_does_not_double_count():
    vfs = VirtualFS()
    vfs.write("/tmp/a.txt", "1234")
    assert vfs.find("/tmp", "*.txt") == ["/tmp/a.txt"]
    assert vfs.du("/tmp") == 4096 + 4
