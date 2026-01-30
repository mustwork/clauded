# Infrastructure Testing Strategy

## Overview

This document describes the testing approach for Ansible-based infrastructure provisioning in clauded.

## Test Coverage Layers

### Layer 1: Unit Tests (Python)

**Location**: `tests/test_provisioner.py`, `tests/test_config.py`, etc.

**Coverage**:
- Role selection logic
- Playbook generation
- Configuration validation
- CLI option parsing
- Lima config generation

**Approach**: Mocked subprocess calls, file I/O

**Status**: ✓ Complete (761 tests passing)

### Layer 2: Infrastructure Integration Tests

**Status**: ⚠️ Manual Verification Required

**Why Manual**:
- Ansible roles provision actual VMs with real software installations
- Integration tests require:
  - Lima VM creation (60+ seconds)
  - Full Ansible provisioning (30-90 seconds)
  - SSH access to verify installed tools
  - VM teardown and cleanup
- Not practical for CI/CD (slow, resource-intensive)
- Better suited for acceptance testing

**Current Verification Process**:
1. Developer creates test VM: `clauded create --config .clauded.yaml`
2. SSH into VM: `clauded shell`
3. Manually verify tool availability:
   - Node.js: `node --version`
   - npm: `npm --version`
   - corepack: `corepack --version`
   - yarn: `yarn --version`
   - pnpm: `pnpm --version`
4. Test package manager operations (install, run, etc.)
5. Destroy test VM: `clauded destroy`

### Layer 3: End-to-End Acceptance Tests

**Status**: User Responsibility

**Approach**: Real project workflows in provisioned VMs

**Examples**:
- Clone project → `clauded create` → `clauded shell` → run build/test commands
- Verify all advertised package managers work
- Test cross-tool integration (e.g., Python + Node.js projects)

## Known Test Gaps

### INFRASTRUCTURE-001: Corepack Integration Tests

**Issue**: No automated tests verify corepack/yarn/pnpm availability after Node.js provisioning

**Severity**: Medium (8/10 for thoroughness, but manual testing is standard for infrastructure)

**Rationale for Manual Approach**:
- Infrastructure provisioning inherently requires real VMs
- Ansible role idempotency ensures repeatability
- Pattern-based implementation (following existing role patterns)
- Unit tests verify role selection and playbook generation
- Manual verification catches environment-specific issues better than mocks

**Mitigation**:
- Follow established Ansible role patterns (documented in docs/architecture.md)
- Use `creates` flag for idempotency verification
- Include verification tasks in all installation roles
- Document manual verification steps (above)

**Future Consideration**:
If integration test automation becomes priority:
- Use Molecule framework for Ansible role testing
- Integrate with Lima for VM provisioning
- Requires significant CI/CD infrastructure investment
- Would add 5+ minutes per test run

### INFRASTRUCTURE-002: Cross-Tool Integration Tests

**Issue**: No automated tests verify tool combinations (e.g., Python + Node.js)

**Severity**: Low (5/10)

**Rationale**:
- Roles are independent (no cross-dependencies in code)
- User workflows vary widely (impossible to test all combinations)
- Manual testing during feature development sufficient

**Mitigation**:
- Document common tool combinations in README
- Encourage users to report incompatibilities
- Fix issues reactively based on real usage patterns

## Testing Best Practices for Infrastructure

1. **Unit test business logic**: Role selection, config validation, CLI parsing
2. **Mock external dependencies**: subprocess, file I/O, API calls
3. **Document manual verification**: Clear steps for developers
4. **Follow established patterns**: Reduces need for per-role testing
5. **Make roles idempotent**: Supports safe manual testing/reprovisioning
6. **Include verification tasks**: Every install role should verify success

## Continuous Improvement

**When to Add Automated Infrastructure Tests**:
- Regression discovered in production usage
- Pattern changes across multiple roles
- Critical security-sensitive operations
- Frequent breakage requiring automated checks

**When to Keep Manual Testing**:
- One-time feature additions following established patterns
- Environment-specific configurations (Alpine vs Ubuntu)
- Exploratory testing for new tools/versions
- Acceptance testing for user-facing workflows

## References

- Ansible Testing Documentation: https://docs.ansible.com/ansible/latest/dev_guide/testing.html
- Molecule Framework: https://molecule.readthedocs.io/
- Test-Kitchen (alternative): https://kitchen.ci/
