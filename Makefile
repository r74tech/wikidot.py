FORMAT_DIR = src
DOCS_SOURCE = docs/source
DOCS_BUILD = docs/build

release_from-develop:
	gh pr create --base main --head develop --title "Release v$(version)"
	gh pr merge --auto
	gh release create $(version) --target main --latest --generate-notes --title "$(version)"

build:
	rm -rf dist
	pip install -e .[build]
	python -m build

update-version:
	@echo "Updating version to $(version)"
	@sed -i.bak 's/^version = ".*"/version = "$(version)"/' pyproject.toml && rm pyproject.toml.bak
	@sed -i.bak 's/__version__ = ".*"/__version__ = "$(version)"/' src/wikidot/__init__.py && rm src/wikidot/__init__.py.bak
	@echo "Version updated in pyproject.toml and src/wikidot/__init__.py"

release:
	echo "Releasing version $(version)"
	make update-version version=$(version)
	make format
	make lint-fix
	git add .
	git commit -m 'release: $(version)' --allow-empty
	git push origin develop
	make release_from-develop version=$(version)

commit:
	make format
	git add .
	git commit -m '$(message)'

format:
	pip install -e .[format]
	python -m ruff format $(FORMAT_DIR)

lint:
	pip install -e .[lint]
	python -m ruff check $(FORMAT_DIR)
	python -m mypy $(FORMAT_DIR) --install-types --non-interactive

lint-fix:
	pip install -e .[lint]
	python -m ruff check $(FORMAT_DIR) --fix

# ドキュメント関連のコマンド
docs-install:
	pip install -e .[docs]

docs-build:
	make docs-install
	sphinx-build -b html $(DOCS_SOURCE) $(DOCS_BUILD)

docs-clean:
	rm -rf $(DOCS_BUILD)

docs-serve:
	cd $(DOCS_BUILD) && python -m http.server

docs-github:
	make docs-clean
	make docs-build
	touch $(DOCS_BUILD)/.nojekyll
	@echo "GitHub Pages用のドキュメントが生成されました。docs/buildディレクトリの内容をgh-pagesブランチにプッシュしてください。"

PHONY: build release release_from-develop update-version format commit docs-install docs-build docs-clean docs-serve docs-github