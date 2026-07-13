"""Tests for ProfileProvisioner and RecordOnlyProvisioner (TD-04-T2)."""

from app.runtime import (
    ProfileProvisioner,
    ProvisioningAction,
    RecordOnlyProvisioner,
)


class TestRecordOnlyProvisioner:
    def test_create_profile_recorded(self):
        prov = RecordOnlyProvisioner()
        prov.create_profile("wk_test-agent")
        actions = prov.get_actions()
        assert len(actions) == 1
        assert actions[0].action == "create_profile"
        assert actions[0].profile_name == "wk_test-agent"

    def test_write_soul_recorded(self):
        prov = RecordOnlyProvisioner()
        soul = "# SOUL\nYou are a frontend engineer."
        prov.write_soul("wk_test-agent", soul)
        actions = prov.get_actions()
        assert actions[0].action == "write_soul"
        assert actions[0].details["soul_length"] == len(soul)
        # Soul content should NOT be stored in details
        assert "soul_md" not in actions[0].details
        assert soul not in str(actions[0].details)

    def test_configure_recorded(self):
        prov = RecordOnlyProvisioner()
        prov.configure(
            "wk_test-agent",
            model="deepseek/deepseek-chat",
            toolsets=["terminal", "file"],
            mcp=["github"],
        )
        actions = prov.get_actions()
        assert actions[0].action == "configure"
        assert actions[0].details["model"] == "deepseek/deepseek-chat"
        assert actions[0].details["toolsets"] == ["terminal", "file"]
        assert actions[0].details["mcp"] == ["github"]

    def test_install_skills_recorded(self):
        prov = RecordOnlyProvisioner()
        prov.install_skills("wk_test-agent", ["react-components", "testing"])
        actions = prov.get_actions()
        assert actions[0].action == "install_skills"
        assert actions[0].details["skills"] == ["react-components", "testing"]

    def test_write_credentials_recorded_without_values(self):
        """SECURITY: credential values must never appear in recorded actions."""
        prov = RecordOnlyProvisioner()
        creds = {
            "GITHUB_TOKEN": "ghp_secret_value_123",
            "PLATFORM_TOKEN": "pk_live_secret_456",
        }
        prov.write_credentials("wk_test-agent", creds)
        actions = prov.get_actions()
        assert actions[0].action == "write_credentials"
        assert set(actions[0].details["credential_keys"]) == {
            "GITHUB_TOKEN",
            "PLATFORM_TOKEN",
        }
        # Credential values must NOT appear anywhere in the recorded action
        action_str = str(actions[0].details)
        assert "ghp_secret_value_123" not in action_str
        assert "pk_live_secret_456" not in action_str

    def test_full_provisioning_sequence(self):
        """Test the complete provisioning call sequence."""
        prov = RecordOnlyProvisioner()
        profile = "wk_test-agent"

        prov.create_profile(profile)
        prov.write_soul(profile, "# SOUL\nYou are a frontend engineer.")
        prov.configure(
            profile,
            model="deepseek/deepseek-chat",
            toolsets=["terminal", "file"],
            mcp=["github"],
        )
        prov.install_skills(profile, ["react-components"])
        prov.write_credentials(profile, {"GITHUB_TOKEN": "secret"})

        actions = prov.get_actions()
        assert len(actions) == 5
        assert [a.action for a in actions] == [
            "create_profile",
            "write_soul",
            "configure",
            "install_skills",
            "write_credentials",
        ]
        # All actions target the same profile
        assert all(a.profile_name == profile for a in actions)

    def test_clear(self):
        prov = RecordOnlyProvisioner()
        prov.create_profile("test")
        assert len(prov.get_actions()) == 1
        prov.clear()
        assert len(prov.get_actions()) == 0

    def test_no_filesystem_side_effects(self, tmp_path):
        """RecordOnlyProvisioner should not create any files."""
        import os

        prov = RecordOnlyProvisioner()
        prov.create_profile("test_profile")
        prov.write_soul("test_profile", "# SOUL")
        prov.configure(
            "test_profile",
            model="test",
            toolsets=["terminal"],
            mcp=[],
        )
        prov.install_skills("test_profile", ["skill1"])
        prov.write_credentials("test_profile", {"KEY": "value"})

        # No files should have been created in tmp_path
        assert os.listdir(tmp_path) == []

    def test_add_capability_recorded(self):
        """add_capability is recorded with correct details."""
        prov = RecordOnlyProvisioner()
        bundle = {
            "toolsets": ["web", "image_gen"],
            "skills": ["marketing"],
            "mcp": [],
            "required_credentials": ["SOCIAL_API_KEY"],
            "risk_gate": "approval",
        }
        prov.add_capability("wk_test-agent", "social_content", bundle)
        actions = prov.get_actions()
        assert len(actions) == 1
        assert actions[0].action == "add_capability"
        assert actions[0].details["capability_key"] == "social_content"
        assert actions[0].details["toolsets"] == ["web", "image_gen"]
        assert actions[0].details["skills"] == ["marketing"]
        assert actions[0].details["required_credentials"] == ["SOCIAL_API_KEY"]

    def test_reload_gateway_recorded(self):
        """reload_gateway is recorded."""
        prov = RecordOnlyProvisioner()
        prov.reload_gateway("wk_test-agent")
        actions = prov.get_actions()
        assert len(actions) == 1
        assert actions[0].action == "reload_gateway"
        assert actions[0].profile_name == "wk_test-agent"

    def test_full_provisioning_sequence_including_capability_upgrade(self):
        """Complete provisioning + capability upgrade sequence."""
        prov = RecordOnlyProvisioner()
        profile = "wk_test-agent"

        # Initial provisioning
        prov.create_profile(profile)
        prov.write_soul(profile, "# SOUL\nYou are a frontend engineer.")
        prov.configure(
            profile,
            model="deepseek/deepseek-chat",
            toolsets=["terminal", "file"],
            mcp=[],
        )
        prov.install_skills(profile, ["react-components"])
        prov.write_credentials(profile, {"GITHUB_TOKEN": "secret"})

        # Capability upgrade
        bundle = {
            "toolsets": ["web", "image_gen"],
            "skills": ["marketing"],
            "mcp": [],
            "required_credentials": ["SOCIAL_API_KEY"],
            "risk_gate": "approval",
        }
        prov.add_capability(profile, "social_content", bundle)
        prov.reload_gateway(profile)

        actions = prov.get_actions()
        assert len(actions) == 7
        assert [a.action for a in actions] == [
            "create_profile",
            "write_soul",
            "configure",
            "install_skills",
            "write_credentials",
            "add_capability",
            "reload_gateway",
        ]
        assert all(a.profile_name == profile for a in actions)


class TestProtocol:
    def test_record_only_satisfies_protocol(self):
        """RecordOnlyProvisioner should satisfy ProfileProvisioner protocol."""
        prov: ProfileProvisioner = RecordOnlyProvisioner()
        # Just verify it doesn't raise
        prov.create_profile("test")
