# TASK-008 discovery

The inherited `uninstall()` unconditionally calls `dest.unlink()` whenever the destination exists.
That removes post-install user edits and follows no ownership record. It also leaves the Claude Code
`skills/agentrouter/` directory empty. Install reads/writes through destination symlinks and permits
constructed `PluginFile.dest` traversal. Backups are not restored if the managed destination was
manually removed, and an existing backup can be overwritten by a later force install.

