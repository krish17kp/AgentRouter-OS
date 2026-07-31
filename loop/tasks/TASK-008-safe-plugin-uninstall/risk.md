# TASK-008 risk review

Primary risk is destructive removal outside AgentRouter ownership. The implementation must never
use recursive deletion, must validate packaged and destination relative paths, must reject link or
reparse-point components, and must compare current contents with the bundled payload before unlink.
Backup collision or ambiguous ownership fails closed. Empty-directory cleanup is restricted to a
plugin-declared directory below its destination root and uses a single non-recursive `rmdir`.

