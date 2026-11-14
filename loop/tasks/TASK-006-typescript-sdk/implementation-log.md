# Implementation log — TASK-006

## Files (all new under sdk/typescript/)
- src/index.ts (AgentRouterClient + AgentRouterError + types)
- test/client.test.ts (7 node:test contract tests, mock fetch)
- package.json (type module; scripts typecheck/test; devDeps typescript + @types/node)
- tsconfig.json (strict, allowImportingTsExtensions, noEmit)
- README.md
- .gitignore: added node_modules/ + *.tsbuildinfo

## Parity bug caught by tests (fixed)
Initial route() defaulted noLog to undefined -> clean() dropped it, so body omitted no_log.
Python SDK always sends no_log:false (default False; _clean keeps False). Fixed:
`no_log: opts.noLog ?? false`. Also fixed npm test script to `test/*.test.ts` (directory
form dropped the --experimental-strip-types flag into subprocesses -> MODULE_NOT_FOUND).

## Verify: typecheck clean; 7/7 tests pass; python pytest 426 passed (untouched).
