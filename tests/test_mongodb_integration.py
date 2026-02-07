"""Integration tests for MongoDB provisioning support.

This module tests the end-to-end integration of MongoDB tools support,
from configuration to role selection in the provisioner.
"""

from hypothesis import given
from hypothesis import strategies as st

from clauded.config import Config
from clauded.lima import LimaVM
from clauded.provisioner import Provisioner


class TestMongoDBIntegration:
    """Integration tests for MongoDB tools provisioning."""

    def test_mongodb_in_config_triggers_role_inclusion(self) -> None:
        """MongoDB in databases list causes mongodb role to be selected."""
        config = Config(
            vm_name="test-mongodb",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=["mongodb"],
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_base_roles()

        assert "mongodb" in roles
        assert "common" in roles

    def test_mongodb_with_other_databases(self) -> None:
        """MongoDB role coexists with other database roles."""
        config = Config(
            vm_name="test-multi-db",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=["postgresql", "mongodb", "redis"],
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_base_roles()

        assert "mongodb" in roles
        assert "postgresql" in roles
        assert "redis" in roles

    def test_mongodb_absent_when_not_configured(self) -> None:
        """MongoDB role excluded when mongodb not in databases."""
        config = Config(
            vm_name="test-no-mongodb",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=["postgresql", "mysql"],
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_base_roles()

        assert "mongodb" not in roles

    @given(
        databases=st.lists(
            st.sampled_from(["postgresql", "mysql", "redis", "sqlite", "mongodb"]),
            unique=True,
            max_size=5,
        )
    )
    def test_mongodb_role_selection_property(self, databases: list[str]) -> None:
        """Property: mongodb role present if and only if mongodb in databases list."""
        config = Config(
            vm_name="test-property",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=databases,
        )
        vm = LimaVM(config)
        provisioner = Provisioner(config, vm)

        roles = provisioner._get_base_roles()

        # Property: mongodb in roles <=> mongodb in databases
        if "mongodb" in databases:
            assert "mongodb" in roles
        else:
            assert "mongodb" not in roles

    @given(
        databases=st.lists(
            st.sampled_from(["postgresql", "mysql", "redis", "sqlite", "mongodb"]),
            unique=True,
            min_size=1,
        )
    )
    def test_database_roles_order_independence(self, databases: list[str]) -> None:
        """Property: database roles are included regardless of order in config."""
        # Create two configs with same databases in different orders
        config1 = Config(
            vm_name="test-order-1",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=databases,
        )
        config2 = Config(
            vm_name="test-order-2",
            cpus=2,
            memory="4GiB",
            disk="10GiB",
            mount_host="/test/project",
            mount_guest="/workspace",
            databases=list(reversed(databases)),
        )

        vm1 = LimaVM(config1)
        vm2 = LimaVM(config2)
        provisioner1 = Provisioner(config1, vm1)
        provisioner2 = Provisioner(config2, vm2)

        roles1 = provisioner1._get_base_roles()
        roles2 = provisioner2._get_base_roles()

        # Property: same database roles included regardless of order
        db_roles1 = [r for r in roles1 if r in databases]
        db_roles2 = [r for r in roles2 if r in databases]

        assert set(db_roles1) == set(db_roles2)
        if "mongodb" in databases:
            assert "mongodb" in roles1
            assert "mongodb" in roles2
