"""Distribution provider infrastructure for multi-distro support.

This module provides:
- DistroProvider protocol defining distro-specific operations
- AlpineProvider and UbuntuProvider implementations
- Factory function for provider instantiation
"""

from typing import Protocol

# Supported Linux distributions
SUPPORTED_DISTROS = ["alpine", "ubuntu"]


class DistroProvider(Protocol):
    """Protocol for distribution-specific operations.

    CONTRACT:
      Purpose: Define interface for distro-specific behavior (cloud images,
               role selection, validation). Each distro implementation provides
               metadata and operations specific to that distribution.

      Implementations must provide all methods below.
    """

    @property
    def name(self) -> str:
        """Get distribution identifier.

        CONTRACT:
          Inputs: None
          Outputs:
            - name: string, lowercase distro identifier matching SUPPORTED_DISTROS
              Example: "alpine", "ubuntu"
          Invariants:
            - name is constant for provider instance
            - name is member of SUPPORTED_DISTROS
          Properties:
            - Identity: same provider instance always returns same name
        """
        ...

    @property
    def display_name(self) -> str:
        """Get human-readable distribution name for UI display.

        CONTRACT:
          Inputs: None
          Outputs:
            - display_name: string, capitalized name for user-facing display
              Example: "Alpine Linux", "Ubuntu"
          Invariants:
            - display_name is constant for provider instance
          Properties:
            - Identity: same provider instance always returns same display_name
        """
        ...

    def get_cloud_image(self) -> dict[str, str]:
        """Get cloud image metadata for this distribution.

        CONTRACT:
          Inputs: None
          Outputs:
            - cloud_image: dictionary with keys 'url', 'version', 'arch'
              Example: {"url": "https://...", "version": "3.21.0", "arch": "aarch64"}
          Invariants:
            - Dictionary contains exactly keys: 'url', 'version', 'arch'
            - All values are non-empty strings
            - url starts with 'https://'
          Properties:
            - Stability: same provider instance returns same metadata (pinned versions)
          Algorithm:
            Retrieves metadata from downloads.yml via get_cloud_image(distro_name)
        """
        ...

    def get_ansible_role_prefix(self) -> str:
        """Get prefix for distro-specific Ansible role names.

        CONTRACT:
          Inputs: None
          Outputs:
            - prefix: empty string (role suffix pattern used instead)
              Note: Returns "" because role selection uses suffix pattern
          Invariants:
            - prefix is empty string for all current implementations
          Properties:
            - Consistency: all providers return same value
          Algorithm:
            Returns empty string. Role selection uses f"{role}-{distro}".
        """
        ...

    def validate_environment(self, env: dict) -> None:
        """Validate environment configuration for distro-specific constraints.

        CONTRACT:
          Inputs:
            - env: dictionary containing environment configuration
              Keys may include: python, node, java, kotlin, rust, go, dart, c,
                                tools, databases, frameworks
          Outputs:
            - None (raises exception on validation failure)
          Invariants:
            - Raises ConfigValidationError if any distro-specific constraint violated
            - No side effects on valid input
          Properties:
            - All-or-nothing: either succeeds completely or raises error
          Algorithm:
            Currently no-op for Alpine and Ubuntu (all supported).
            Future distros may add validation (e.g., version constraints)
        """
        ...


class AlpineProvider:
    """Alpine Linux distribution provider.

    Provides Alpine-specific metadata and operations.
    """

    @property
    def name(self) -> str:
        """Get distribution identifier 'alpine'.

        CONTRACT:
          Inputs: None
          Outputs:
            - name: "alpine" (string literal)
          Invariants:
            - Always returns "alpine"
        """
        return "alpine"

    @property
    def display_name(self) -> str:
        """Get human-readable name 'Alpine Linux'.

        CONTRACT:
          Inputs: None
          Outputs:
            - display_name: "Alpine Linux" (string literal)
          Invariants:
            - Always returns "Alpine Linux"
        """
        return "Alpine Linux"

    def get_cloud_image(self) -> dict[str, str]:
        """Get Alpine cloud image metadata from downloads.yml.

        CONTRACT:
          Inputs: None
          Outputs:
            - cloud_image: dictionary from downloads.yml['alpine_image']
              Contains keys: 'url', 'version', 'arch'
          Invariants:
            - Dictionary structure matches downloads.yml alpine_image entry
          Algorithm:
            Calls get_cloud_image('alpine') from downloads module
        """
        from .downloads import get_cloud_image

        return get_cloud_image("alpine")

    def get_ansible_role_prefix(self) -> str:
        """Get role prefix (empty string, uses suffix pattern).

        CONTRACT:
          Inputs: None
          Outputs:
            - prefix: "" (empty string)
        """
        return ""

    def validate_environment(self, env: dict) -> None:
        """Validate environment (no-op, all environments supported).

        CONTRACT:
          Inputs:
            - env: dictionary (ignored)
          Outputs:
            - None
          Algorithm:
            No validation needed - Alpine supports all configured environments
        """
        pass


class UbuntuProvider:
    """Ubuntu distribution provider.

    Provides Ubuntu-specific metadata and operations.
    """

    @property
    def name(self) -> str:
        """Get distribution identifier 'ubuntu'.

        CONTRACT:
          Inputs: None
          Outputs:
            - name: "ubuntu" (string literal)
          Invariants:
            - Always returns "ubuntu"
        """
        return "ubuntu"

    @property
    def display_name(self) -> str:
        """Get human-readable name 'Ubuntu'.

        CONTRACT:
          Inputs: None
          Outputs:
            - display_name: "Ubuntu" (string literal)
          Invariants:
            - Always returns "Ubuntu"
        """
        return "Ubuntu"

    def get_cloud_image(self) -> dict[str, str]:
        """Get Ubuntu cloud image metadata from downloads.yml.

        CONTRACT:
          Inputs: None
          Outputs:
            - cloud_image: dictionary from downloads.yml['ubuntu_image']
              Contains keys: 'url', 'version', 'arch'
          Invariants:
            - Dictionary structure matches downloads.yml ubuntu_image entry
          Algorithm:
            Calls get_cloud_image('ubuntu') from downloads module
        """
        from .downloads import get_cloud_image

        return get_cloud_image("ubuntu")

    def get_ansible_role_prefix(self) -> str:
        """Get role prefix (empty string, uses suffix pattern).

        CONTRACT:
          Inputs: None
          Outputs:
            - prefix: "" (empty string)
        """
        return ""

    def validate_environment(self, env: dict) -> None:
        """Validate environment (no-op, all environments supported).

        CONTRACT:
          Inputs:
            - env: dictionary (ignored)
          Outputs:
            - None
          Algorithm:
            No validation needed - Ubuntu supports all configured environments
        """
        pass


def get_distro_provider(distro: str) -> DistroProvider:
    """Factory function to get appropriate distribution provider.

    CONTRACT:
      Inputs:
        - distro: string, distribution identifier
          Must be member of SUPPORTED_DISTROS
      Outputs:
        - provider: DistroProvider implementation instance
          AlpineProvider if distro == 'alpine'
          UbuntuProvider if distro == 'ubuntu'
      Invariants:
        - Raises ValueError if distro not in SUPPORTED_DISTROS
        - Returned provider.name equals input distro
      Properties:
        - Deterministic: same distro string always returns same provider type
        - Complete: handles all values in SUPPORTED_DISTROS
      Algorithm:
        1. Check if distro in providers dictionary
        2. If not found, raise ValueError with supported distros list
        3. Return provider instance from dictionary
    """
    providers: dict[str, DistroProvider] = {
        "alpine": AlpineProvider(),
        "ubuntu": UbuntuProvider(),
    }

    if distro not in providers:
        raise ValueError(
            f"Unsupported distro: {distro}. Supported: {', '.join(SUPPORTED_DISTROS)}"
        )

    return providers[distro]
