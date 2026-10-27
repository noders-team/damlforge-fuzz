LICENSE_MARKER := Licensed under the Apache License, Version 2.0

.PHONY: license-check

license-check:
	@missing=$$(git ls-files --cached --others --exclude-standard -- 'src/*.py' 'tests/*.py' 'scripts/*.py' \
		| while read -r file; do head -n 20 "$$file" | grep -q "$(LICENSE_MARKER)" || echo "$$file"; done); \
	if [ -n "$$missing" ]; then \
		echo "Missing Apache-2.0 license header:"; echo "$$missing"; exit 1; \
	fi; \
	echo "All Python files have the Apache-2.0 license header."
