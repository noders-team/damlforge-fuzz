# Import bug b28

This folder has one small program that shows an import bug in DamlForge `0413ac6` (`forge_version` 0.0.12).

The number continues b01 to b27 ([the 20000-input analysis](../../reports/2026-10-19T18-45-34Z/analysis.md), [the loop report analysis](../../reports/2026-10-20T16-34-28Z/analysis.md)).
This is category C from that analysis: correct-looking code makes forge crash with a Python traceback, where a DF error would be the right answer.

It was found by hand, checking import forms that the fuzzer's own rules rarely produce (`import` and `from X import Y` are 2 of 16 statement choices in `mutate.py`, so they are rare in random inputs). It is not fuzzer output.

Before writing this up, the two import bugs found in the first report, b13 (`import` inside a function) and b14 (a typo in a `from forge.X import ...` line), were checked again and are now fixed: both get a proper `DF1213` error on `forge_version` 0.0.12.

## b28: a relative import crashes instead of a DF error

```python
from . import models
```

`from . import models` is a relative import: valid Python, and the kind of line a user might write by habit from another Python project. forge has no concept of packages, so this should get a DF error, the same way `from str.models import ...` already gets `DF1213: No module named str.models`.

Instead, forge crashes before its own import checks run, while building the module's scope:

```
$ damlforge-fuzz check bugs/imports
CRASH    check  bugs/imports/b28_relative_import.vy  AttributeError 'NoneType' object has no attribute 'split' at forge/builtin_stubs.py:150
```

The cause, in forge's source:

```
forge/semantics/__init__.py:9, analyze_module
  -> forge/builtin_stubs.py:162, scope_of
  -> forge/builtin_stubs.py:155, _stub_imports
  -> forge/builtin_stubs.py:150, _root
       return module.split(".", 1)[0]
```

`_root` assumes `stmt.module` is always a string. Python's parser sets `ImportFrom.module` to `None` for a relative import with no name after the dots (`from . import X`, or `from .. import X`), so `_root(None)` crashes.
`from .models import X` does not crash this line (its `module` is the string `"models"`), but forge then treats it as if `models` were a top-level module, which is a separate, not yet written up, question of whether `DF1213` fires correctly for it.

## Other import forms checked and found OK on 0.0.12

Checked by hand alongside b28, none crashed or showed a new problem: `import math as m`, `from forge.models import Party as P` (rejected with a clear `DF1213` explaining Daml has no per-symbol alias), `from forge.models import Party, NotARealName` (rejected with `DF1213: No name NotARealName in module forge.models`), an `import` after other top-level code, an `import` inside `if True:`, `from forge.models import *`, and a plain `import forge.models`.
