"""The browser-test harness port: one block of ports per checkout, one port per xdist worker."""

from pathlib import Path

from tests.ui.harness.ports import PORTS_PER_CHECKOUT, base_port, harness_port


def test_base_port_is_stable_for_a_checkout():
    checkout = Path("/home/dev/.herdr/worktrees/haywire-repo/fix-edge-drag")
    assert base_port(checkout) == base_port(checkout)


def test_two_checkouts_get_disjoint_blocks():
    main = base_port(Path("/Volumes/Ddrive/haywire/haywire-repo"))
    worktree = base_port(Path("/Users/dev/.herdr/worktrees/haywire-repo/chore-parallel-work"))
    assert abs(main - worktree) >= PORTS_PER_CHECKOUT


def test_base_port_stays_clear_of_the_studio_and_ephemeral_ports():
    for name in ("a", "b", "fix-edge-drag", "feat-carrier-metadata", "x" * 200):
        port = base_port(Path("/w") / name)
        assert port >= 10000
        assert port + PORTS_PER_CHECKOUT <= 20000
        assert port % PORTS_PER_CHECKOUT == 0


def test_each_worker_gets_its_own_port_in_the_block():
    checkout = Path("/w/fix-edge-drag")
    base = base_port(checkout)
    assert harness_port(checkout, "") == base
    assert harness_port(checkout, "gw0") == base
    assert harness_port(checkout, "gw3") == base + 3
