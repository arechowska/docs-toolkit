.PHONY: install check fix

install:
	cp tools/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Хук установлен"

check:
	python3 tools/doccheck.py

fix:
	python3 tools/doccheck.py --fix
