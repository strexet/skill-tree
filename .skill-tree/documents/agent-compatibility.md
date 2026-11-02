# Agent Compatibility

`.skill-tree/config/providers.json` owns provider IDs, detection, destinations, optional bridges and official discovery references. Provider-required directories retain exact spelling. The source release changes no provider support claim; matrix entries describe discovery configuration rather than native runtime qualification for every release.

Local project-scoped copy installation supports matrix destinations. Soft providers require explicit selection. Generic installation uses the explicit target root without a native-discovery claim. Global, symlink and upstream passthrough specialization are unsupported; the installer never silently forwards uncomposed source templates. Temporary installation/bridge fixtures establish local filesystem behavior only. Actual provider/model behavior remains separately unqualified.
