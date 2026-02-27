import json
from pathlib import Path

from openclaw_skill_deps.scanners import (
    ProjectSignals,
    discover_projects,
    parse_dockerfile_installs,
    parse_package_json_deps,
    parse_requirements_txt,
    scan_project_dir,
)


class TestScanProjectDir:
    def test_empty_dir(self, tmp_path):
        sig = scan_project_dir(tmp_path)
        assert sig.has_package_json is False
        assert sig.npm_deps == []
        assert sig.pip_deps == []

    def test_node_project(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"express": "^4.0"}}),
            encoding="utf-8",
        )
        sig = scan_project_dir(tmp_path)
        assert sig.has_package_json is True
        assert "express" in sig.npm_deps

    def test_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text("requests\nflask>=2.0\n", encoding="utf-8")
        sig = scan_project_dir(tmp_path)
        assert sig.has_pyproject is True
        assert sig.has_requirements is True
        assert "requests" in sig.pip_deps
        assert "flask" in sig.pip_deps

    def test_docker_project(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.12", encoding="utf-8")
        sig = scan_project_dir(tmp_path)
        assert sig.has_dockerfile is True

    def test_all_present(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
        (tmp_path / "Dockerfile").write_text("", encoding="utf-8")
        sig = scan_project_dir(tmp_path)
        assert all([sig.has_package_json, sig.has_pyproject, sig.has_requirements, sig.has_dockerfile])


class TestParseDockerfileInstalls:
    def test_apt_get(self, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text(
            "FROM ubuntu:22.04\nRUN apt-get update && apt-get install -y curl git vim\n",
            encoding="utf-8",
        )
        pkgs = parse_dockerfile_installs(df)
        assert set(pkgs["apt"]) >= {"curl", "git", "vim"}

    def test_apk_add(self, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text("FROM alpine:3.18\nRUN apk add --no-cache bash curl\n", encoding="utf-8")
        pkgs = parse_dockerfile_installs(df)
        assert set(pkgs["apk"]) >= {"bash", "curl"}

    def test_missing_file(self, tmp_path):
        assert parse_dockerfile_installs(tmp_path / "nonexistent") == {"apt": [], "apk": []}

    def test_empty_dockerfile(self, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text("FROM scratch\n", encoding="utf-8")
        assert parse_dockerfile_installs(df) == {"apt": [], "apk": []}

    def test_filters_flags(self, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text("RUN apt-get install -y --no-install-recommends libfoo libbar\n", encoding="utf-8")
        pkgs = parse_dockerfile_installs(df)
        assert "libfoo" in pkgs["apt"]
        assert "libbar" in pkgs["apt"]
        for p in pkgs["apt"]:
            assert not p.startswith("-")


class TestParseRequirementsTxt:
    def test_basic(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("requests\nflask>=2.0\nnumpy==1.24\n", encoding="utf-8")
        pkgs = parse_requirements_txt(req)
        assert pkgs == ["requests", "flask", "numpy"]

    def test_comments_and_blanks(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("# comment\n\nrequests\n  \n", encoding="utf-8")
        assert parse_requirements_txt(req) == ["requests"]

    def test_flags_skipped(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("-r base.txt\n--index-url https://x\nfoo\n", encoding="utf-8")
        assert parse_requirements_txt(req) == ["foo"]

    def test_extras(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("package[extra1,extra2]>=1.0\n", encoding="utf-8")
        assert parse_requirements_txt(req) == ["package"]

    def test_missing_file(self, tmp_path):
        assert parse_requirements_txt(tmp_path / "nope") == []


class TestParsePackageJsonDeps:
    def test_basic(self, tmp_path):
        pj = tmp_path / "package.json"
        pj.write_text(
            json.dumps({
                "dependencies": {"express": "^4.0", "cors": "^2.0"},
                "devDependencies": {"jest": "^29.0"},
            }),
            encoding="utf-8",
        )
        deps = parse_package_json_deps(pj)
        assert set(deps) == {"express", "cors", "jest"}

    def test_empty_deps(self, tmp_path):
        pj = tmp_path / "package.json"
        pj.write_text("{}", encoding="utf-8")
        assert parse_package_json_deps(pj) == []

    def test_missing_file(self, tmp_path):
        assert parse_package_json_deps(tmp_path / "nope") == []

    def test_malformed_json(self, tmp_path):
        pj = tmp_path / "package.json"
        pj.write_text("not json", encoding="utf-8")
        assert parse_package_json_deps(pj) == []


class TestDiscoverProjects:
    def test_empty_dir(self, tmp_path):
        assert discover_projects(tmp_path) == []

    def test_single_project(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        found = discover_projects(tmp_path)
        assert found == [tmp_path]

    def test_nested_monorepo(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        sub = tmp_path / "packages" / "frontend"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text("{}", encoding="utf-8")
        backend = tmp_path / "packages" / "backend"
        backend.mkdir(parents=True)
        (backend / "pyproject.toml").write_text("[project]", encoding="utf-8")

        found = discover_projects(tmp_path)
        assert tmp_path in found
        assert sub in found
        assert backend in found

    def test_skips_node_modules(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        nm = tmp_path / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}", encoding="utf-8")

        found = discover_projects(tmp_path)
        assert nm not in found
        assert len(found) == 1

    def test_skips_dot_git(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM scratch", encoding="utf-8")
        git = tmp_path / ".git" / "hooks"
        git.mkdir(parents=True)

        found = discover_projects(tmp_path)
        assert all(".git" not in str(p) for p in found)

    def test_respects_max_depth(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        deep.mkdir(parents=True)
        (deep / "package.json").write_text("{}", encoding="utf-8")

        found = discover_projects(tmp_path, max_depth=3)
        assert deep not in found
