"""Check every bundled theme with the real Foot parser in a Debian environment.

Usage: python3 tests/check_android_foot_themes.py PATH_TO_BUNDLE.tar.gz
Uses isolated temporary template directories; leaves the user's HOME untouched.
"""

import json, os, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
if len(sys.argv) != 2:
    raise SystemExit("Usage: check_android_foot_themes.py BUNDLE.tar.gz")
subprocess.run(["foot", "--version"], check=True)

with tempfile.TemporaryDirectory(prefix='moarchy-foot-') as work:
    work = Path(work)
    with tarfile.open(sys.argv[1]) as tar:
        tar.extractall(work, filter='data')
    omarchy = work / 'moarchy-android/omarchy'
    stage = work / 'next-theme'
    helper = (omarchy / 'bin/omarchy-theme-set-templates').read_text()
    for before, after in [
        ('NEXT_THEME_DIR="$HOME/.local/state/omarchy/current/next-theme"', 'NEXT_THEME_DIR="' + str(stage) + '"'),
        ('USER_TEMPLATES_DIR="$HOME/.config/omarchy/themed"', 'USER_TEMPLATES_DIR="' + str(work / 'empty') + '"')]:
        assert helper.count(before) == 1
        helper = helper.replace(before, after)
    script = work / 'render.sh'; script.write_text(helper)
    env = dict(os.environ, OMARCHY_PATH=str(omarchy), PATH=str(omarchy / 'bin') + ':/usr/bin:/bin')
    passed = []
    for theme in sorted((omarchy / 'themes').iterdir()):
        if not (theme / 'colors.toml').is_file(): continue
        shutil.copytree(theme, stage)
        subprocess.run(['bash', str(script)], env=env, check=True, capture_output=True, timeout=20)
        result = subprocess.run(['foot', '--check-config', '--config=' + str(stage / 'foot.ini')], env=env, capture_output=True, text=True)
        assert result.returncode == 0, theme.name + ': ' + result.stderr
        passed.append(theme.name)
        shutil.rmtree(stage)
    assert passed
    print(json.dumps({'archive': sys.argv[1], 'valid_themes': passed, 'count': len(passed), 'fixture': 'isolated template output and user-template paths; real renderer and Debian Foot parser'}, indent=2))
