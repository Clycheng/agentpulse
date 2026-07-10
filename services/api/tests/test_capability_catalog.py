"""Tests for capability_catalog module (TD-05-T1)."""

import pytest

from app.orchestration.capability_catalog import (
    CATALOG,
    ROLE_BUNDLES,
    _RISK_SEVERITY,
    CapabilityDef,
    get_capability,
    get_role_bundle,
    list_role_bundles,
    resolve_bundle,
    validate_capability_keys,
)


class TestGetCapability:
    def test_get_known_key(self):
        cap = get_capability("write_code")
        assert cap.key == "write_code"
        assert "terminal" in cap.toolsets
        assert cap.risk_gate == "auto"

    def test_get_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown capability key"):
            get_capability("nonexistent")


class TestValidateCapabilityKeys:
    def test_all_valid(self):
        validate_capability_keys(["write_code", "run_tests"])

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown capability keys"):
            validate_capability_keys(["write_code", "bogus"])

    def test_empty_list_ok(self):
        validate_capability_keys([])


class TestResolveBundle:
    def test_single_auto_capability(self):
        bundle = resolve_bundle(["write_code"])
        assert bundle["risk_gate"] == "auto"
        assert set(bundle["toolsets"]) == {"terminal", "file"}

    def test_merge_auto_and_approval_takes_approval(self):
        """write_code (auto) + deploy_prod (approval) → approval"""
        bundle = resolve_bundle(["write_code", "deploy_prod"])
        assert bundle["risk_gate"] == "approval"
        assert "terminal" in bundle["toolsets"]
        assert "file" in bundle["toolsets"]
        assert "PLATFORM_TOKEN" in bundle["required_credentials"]

    def test_merge_auto_and_prohibited_takes_prohibited(self):
        """write_code (auto) + domain_register (prohibited_auto) → prohibited_auto"""
        bundle = resolve_bundle(["write_code", "domain_register"])
        assert bundle["risk_gate"] == "prohibited_auto"

    def test_merge_approval_and_prohibited_takes_prohibited(self):
        """git_push (approval) + domain_register (prohibited_auto) → prohibited_auto"""
        bundle = resolve_bundle(["git_push", "domain_register"])
        assert bundle["risk_gate"] == "prohibited_auto"

    def test_domain_register_always_prohibited(self):
        """domain_register alone is prohibited_auto (花钱+不可逆)"""
        bundle = resolve_bundle(["domain_register"])
        assert bundle["risk_gate"] == "prohibited_auto"
        assert "REGISTRAR_KEY" in bundle["required_credentials"]

    def test_dedup_toolsets_and_creds(self):
        """Merging capabilities with overlapping toolsets/creds deduplicates."""
        # git_push: terminal + GITHUB_TOKEN
        # deploy_prod: terminal + PLATFORM_TOKEN
        bundle = resolve_bundle(["git_push", "deploy_prod"])
        assert bundle["toolsets"] == ["terminal"]
        assert set(bundle["required_credentials"]) == {"GITHUB_TOKEN", "PLATFORM_TOKEN"}

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown capability keys"):
            resolve_bundle(["write_code", "bogus"])

    def test_empty_keys_returns_empty_bundle(self):
        bundle = resolve_bundle([])
        assert bundle == {
            "skills": [],
            "toolsets": [],
            "mcp": [],
            "required_credentials": [],
            "risk_gate": "auto",
        }

    def test_mcp_merged(self):
        """git_push has mcp[github]."""
        bundle = resolve_bundle(["git_push"])
        assert bundle["mcp"] == ["github"]


class TestCatalogSeed:
    """Verify the technical seed (TD-05) is still intact after TD-07 extension."""

    EXPECTED_KEYS = {
        "write_code",
        "run_tests",
        "git_push",
        "deploy_preview",
        "deploy_prod",
        "domain_register",
        "seo_audit",
        "social_content",
    }

    def test_seed_keys_present(self):
        assert self.EXPECTED_KEYS <= set(CATALOG.keys())

    def test_write_code(self):
        cap = CATALOG["write_code"]
        assert set(cap.toolsets) == {"terminal", "file"}
        assert cap.risk_gate == "auto"

    def test_run_tests(self):
        cap = CATALOG["run_tests"]
        assert cap.toolsets == ("terminal",)
        assert cap.risk_gate == "auto"

    def test_git_push(self):
        cap = CATALOG["git_push"]
        assert cap.toolsets == ("terminal",)
        assert cap.mcp == ("github",)
        assert "GITHUB_TOKEN" in cap.required_credentials
        assert cap.risk_gate == "approval"

    def test_deploy_preview(self):
        cap = CATALOG["deploy_preview"]
        assert cap.toolsets == ("terminal",)
        assert "PLATFORM_TOKEN" in cap.required_credentials
        assert cap.risk_gate == "auto"

    def test_deploy_prod(self):
        cap = CATALOG["deploy_prod"]
        assert cap.toolsets == ("terminal",)
        assert "PLATFORM_TOKEN" in cap.required_credentials
        assert cap.risk_gate == "approval"

    def test_domain_register(self):
        cap = CATALOG["domain_register"]
        assert cap.risk_gate == "prohibited_auto"
        assert "REGISTRAR_KEY" in cap.required_credentials

    def test_seo_audit(self):
        cap = CATALOG["seo_audit"]
        assert set(cap.toolsets) == {"terminal", "web"}
        assert cap.risk_gate == "auto"

    def test_social_content(self):
        cap = CATALOG["social_content"]
        # TD-07 reconciliation: image_gen added (generate images for posts).
        assert set(cap.toolsets) == {"web", "image_gen", "vision"}
        assert cap.risk_gate == "approval"


class TestBusinessCatalog:
    """TD-07: every catalog entry is well-formed; business keys present."""

    BUSINESS_KEYS = {
        "customer_service",
        "ticket_management",
        "refund_processing",
        "customer_data_lookup",
        "content_writing",
        "image_creation",
        "email_drafting",
        "email_sending",
        "seo_content",
        "ad_analysis",
        "ad_bidding",
        "data_query",
        "data_analysis",
        "report_generation",
        "web_scraping",
        "resume_screening",
        "jd_generation",
        "interview_prep",
        "onboarding_docs",
        "hr_data_analysis",
        "payroll_processing",
        "contract_review",
        "contract_drafting",
        "compliance_check",
        "expense_analysis",
        "invoice_processing",
        "financial_reporting",
        "payment_execution",
        "task_delegation",
        "meeting_scheduling",
        "project_reporting",
    }

    def test_business_keys_present(self):
        assert self.BUSINESS_KEYS <= set(CATALOG.keys())

    def test_every_entry_wellformed(self):
        for key, cap in CATALOG.items():
            assert cap.key == key, f"{key}: key mismatch"
            assert cap.description.strip(), f"{key}: empty description"
            assert cap.risk_gate in _RISK_SEVERITY, f"{key}: bad risk_gate"

    def test_credentialed_caps_declare_credentials(self):
        # If a capability reaches an external system via MCP, it must declare creds.
        exempt = set()  # none currently — all MCP caps require a credential
        for key, cap in CATALOG.items():
            if cap.mcp and key not in exempt:
                assert cap.required_credentials, f"{key}: MCP cap without credentials"

    def test_payment_execution_is_prohibited(self):
        assert CATALOG["payment_execution"].risk_gate == "prohibited_auto"

    def test_resolve_business_bundle(self):
        bundle = resolve_bundle(["data_query", "data_analysis", "report_generation"])
        assert bundle["risk_gate"] == "auto"
        assert "code_execution" in bundle["toolsets"]
        assert "DB_URL" in bundle["required_credentials"]


class TestRoleBundles:
    def test_all_bundle_keys_exist_in_catalog(self):
        for role, keys in ROLE_BUNDLES.items():
            for key in keys:
                assert key in CATALOG, f"role {role}: unknown capability {key}"

    def test_get_role_bundle_returns_keys(self):
        keys = get_role_bundle("数据分析师")
        assert keys == ["data_query", "data_analysis", "report_generation"]

    def test_get_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown role bundle"):
            get_role_bundle("不存在的岗位")

    def test_list_role_bundles(self):
        names = list_role_bundles()
        assert "客服专员" in names
        assert "前端工程师" in names

    def test_bundle_resolves_without_error(self):
        # Every preset role must resolve into a valid merged bundle.
        for role in ROLE_BUNDLES:
            bundle = resolve_bundle(get_role_bundle(role))
            assert bundle["risk_gate"] in _RISK_SEVERITY
