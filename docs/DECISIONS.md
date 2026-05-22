# Architecture Decision Records (ADRs)

Decision log for Signal Chain project architecture and significant technical choices.

---

## ADR-006: Qt/EGL Library Dependencies in GitHub Actions CI

**Status:** Accepted

**Date:** May 2026

### Context
PyQt6 applications require Qt runtime libraries to function, even in headless (GUI-less) environments. GitHub Actions runners on `ubuntu-latest` do not include these libraries by default, causing import failures when pytest attempts to load PyQt6 modules.

The initial CI workflow failed with:
```
libEGL.so.1: cannot open shared object file: No such file or directory
```

This prevented any PyQt6-dependent tests from running in the automated CI pipeline.

### Decision
Add system-level Qt/EGL library dependencies to the CI workflow via `apt-get install`. Specifically:
- `libegl1` - EGL library
- `libgl1` - OpenGL library
- `libxkbcommon0` - Keyboard input handling
- `libdbus-1-3` - D-Bus daemon (Qt dependency)

Configure Qt to run in offscreen mode using the `QT_QPA_PLATFORM=offscreen` environment variable, which tells Qt to render without accessing a display server.

### Consequences
- **Positive:** CI workflow now successfully imports and tests PyQt6 code in headless runners. Tests that exercise GUI components can run without requiring display virtualization (xvfb).
- **Positive:** Minimal overhead—library installation adds ~2-3 seconds to CI runtime.
- **Negative:** CI environment is no longer a "bare" Python environment; it includes Qt system dependencies that would not be present in minimal deployment targets.
- **Negative:** If Qt library versions in the runner diverge from development environments, compatibility issues may arise.

### Alternatives Considered

1. **Use xvfb (Virtual Framebuffer)**
   - Install and configure xvfb to provide a virtual display
   - More complex setup, higher resource usage
   - Better isolation from host system libraries
   - **Rejected:** Unnecessary complexity for headless testing

2. **Mock PyQt6 in Tests**
   - Mock Qt components during testing, test only business logic
   - Reduces Qt library dependency in CI
   - **Rejected:** We need to verify actual PyQt6 integration, not just business logic

3. **Skip GUI Tests in CI**
   - Mark GUI tests with `@pytest.mark.skip` in CI
   - Reduces CI requirements
   - **Rejected:** Reduces confidence in GUI code quality; defeats purpose of CI

### Related Decisions
- Follows from the choice to use PyQt6 as the UI framework
- Informs the CI/CD strategy for handling framework-specific testing requirements

---
