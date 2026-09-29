---
name: advanced-python-developer
description: >-
  Advanced Python engineering standards for high-performance data systems, clean architecture,
  thread safety, zero-copy Arrow memory layouts, modern typing, and vectorized execution.
---

# Advanced Python Developer Skill

Guidelines and best practices for writing production-grade, highly optimized, and maintainable Python code in LineagIQ.

## Core Architectural Principles

1. **Strict Type Annotations**:
   - Utilize modern Python typing (`typing.Any`, `typing.Protocol`, `typing.Literal`, `typing.Sequence`).
   - Use union operator `A | B` instead of `Union[A, B]`, and `A | None` instead of `Optional[A]`.
   - Leverage `pydantic.BaseModel` (v2) for schema validation, strict parsing, and JSON serialization.

2. **Thread Safety & Shared Memory**:
   - Protect mutable in-memory state and connections using `threading.Lock()` or `threading.RLock()`.
   - Implement thread-safe connection pooling and view caching with TTL and eviction.
   - Avoid global mutable variables without thread-safe synchronization.

3. **High-Performance Vectorized Execution**:
   - Prefer Apache Arrow (`pyarrow`) and columnar vectorized structures over raw Python dictionary iteration.
   - Minimize object allocations and Python-level loops over large datasets (use NumPy/Arrow batch operations).
   - Use generators and stream processing when dealing with unbounded records.

4. **Resource Management**:
   - Always use context managers (`with` statements) for file handles, sockets, and database connections.
   - Gracefully handle connection closures and ephemeral process cleanup.

5. **Testing & Quality Assurance**:
   - Always write tests using `.venv/bin/pytest` with `pytest-asyncio` for async paths.
   - Maintain comprehensive unit and integration coverage for edge cases, invalid inputs, and error states.
