import doccheck


def test_line_number_first_line():
    assert doccheck.line_number("hello world", 3) == 1


def test_line_number_counts_newlines():
    text = "line1\nline2\nline3"
    pos = text.index("line3")
    assert doccheck.line_number(text, pos) == 3


def test_find_files_ignores_matching_folder(tmp_path):
    (tmp_path / "docs" / "old").mkdir(parents=True)
    (tmp_path / "docs" / "old" / "a.md").write_text("# a")

    result = doccheck.find_files(
        [str(tmp_path / "docs")], [str(tmp_path / "docs" / "old")]
    )

    assert result == []


def test_find_files_does_not_match_similar_prefix(tmp_path):
    """Regression test: ignoring 'docs/old' must not exclude 'docs/old_version'."""
    (tmp_path / "docs" / "old").mkdir(parents=True)
    (tmp_path / "docs" / "old" / "a.md").write_text("# a")
    (tmp_path / "docs" / "old_version").mkdir(parents=True)
    (tmp_path / "docs" / "old_version" / "b.md").write_text("# b")

    result = doccheck.find_files(
        [str(tmp_path / "docs")], [str(tmp_path / "docs" / "old")]
    )

    assert str(tmp_path / "docs" / "old_version" / "b.md") in result
    assert str(tmp_path / "docs" / "old" / "a.md") not in result


def test_check_links_flags_broken_link(tmp_path):
    doc = tmp_path / "page.md"
    doc.write_text("See [other](missing.md) for details.")

    issues = doccheck.check_links(str(doc), doc.read_text())

    assert len(issues) == 1
    assert "missing.md" in issues[0][1]


def test_check_links_ignores_external_links(tmp_path):
    doc = tmp_path / "page.md"
    doc.write_text("See [docs](https://example.com/page.md) for details.")

    issues = doccheck.check_links(str(doc), doc.read_text())

    assert issues == []


def test_process_file_applies_fix_rules(tmp_path):
    doc = tmp_path / "page.md"
    doc.write_text("Привет, ёжик!")
    fix_rules = [{"pattern": "ё", "replacement": "е", "description": "ё → е"}]

    issues, fixes = doccheck.process_file(str(doc), fix_rules, [], fix=True)

    assert doc.read_text() == "Привет, ежик!"
    assert fixes == ["ё → е (1×)"]


def test_process_file_reports_check_severity(tmp_path):
    doc = tmp_path / "page.md"
    doc.write_text("![]()")
    check_rules = [{
        "pattern": r"!\[\]\(",
        "description": "Image without alt text",
        "severity": "warn",
    }]

    issues, fixes = doccheck.process_file(str(doc), [], check_rules, fix=False)

    assert fixes == []
    assert len(issues) == 1
    _, description, severity = issues[0]
    assert severity == "warn"
    assert description == "Image without alt text"
