import subprocess


def test_docs_subcommand_is_registered():
    result = subprocess.run(
        ["haywire", "docs", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "library" in result.stdout.lower()
