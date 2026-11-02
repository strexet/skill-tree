# Security and Ownership

Skill Tree has no telemetry. Offline generators, validators and installer dry runs require no external services. Portable metadata stores repository-relative paths and source hashes; credentials, private data and environment dumps remain excluded.

Metadata mutations stay inside the owned `.skill-tree/` directory. Exclusive locking, hash guards and atomic transactions protect interrupted writes. Evidence history never grants authorization. Installer bridges preserve unowned instructions; scoped uninstall preserves unrelated packages. Secrets and private evidence never enter tracked history. External operations, publication and scheduling require explicit developer scope.
