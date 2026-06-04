from bingus_ia.core.types import Injection
from bingus_ia.injections.sandbox import InjectionSandbox


class TestInjectionSandbox:
    def test_valid_injection(self):
        inj = Injection(name="ok", trigger_phrase="x", prompt_override="Use TypeScript always")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is True
        assert err is None

    def test_blocked_rm_rf(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="Run: rm -rf /")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False
        assert "rm" in err

    def test_blocked_drop_table(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="DROP TABLE users")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False
        assert "DROP" in err or "TABLE" in err

    def test_blocked_os_system(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="call os.system('rm')")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False
        assert "os" in err or "system" in err or "blocked" in err

    def test_blocked_subprocess_call(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="subprocess.call('rm')")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False

    def test_disallowed_template_var(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="Use {{secret_key}}")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False
        assert "secret_key" in err

    def test_allowed_template_var(self):
        inj = Injection(name="ok", trigger_phrase="x", prompt_override="Work in {{workspace_dir}}")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is True

    def test_render(self):
        inj = Injection(name="r", trigger_phrase="x", prompt_override="Dir: {{workspace_dir}}")
        result = InjectionSandbox.render(inj, {"workspace_dir": "/home/project", "secret_key": "should-not-appear"})
        assert result == "Dir: /home/project"
        assert "should-not-appear" not in result

    def test_blocked_format(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="format C:")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False

    def test_blocked_shutil_rmtree(self):
        inj = Injection(name="bad", trigger_phrase="x", prompt_override="shutil.rmtree('/')")
        is_valid, err = InjectionSandbox.validate(inj)
        assert is_valid is False
