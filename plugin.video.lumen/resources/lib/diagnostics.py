"""Short failure reports without exception text, locals, tokens or URLs."""
import os
import traceback


def failure_report(error, stage):
    frames = traceback.extract_tb(error.__traceback__)
    locations = ['%s:%s in %s' % (os.path.basename(f.filename), f.lineno, f.name)
                 for f in frames]
    return 'Lumen %s: %s\n%s' % (stage, type(error).__name__, '\n'.join(locations))
