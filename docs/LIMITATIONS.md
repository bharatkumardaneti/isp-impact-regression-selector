# Scope and limitations

- Early working release, verified using a generated grayscale dataset. Real ISP integration and accuracy of supplied contracts are unverified.
- No vendor XML/XSD diff/parser, RAW decoder, calibration model, hardware control, cloud storage client, Imatest integration or perception stack is bundled.
- All frame metadata and decisions reside in memory. Input hashing reads all catalog files and adds I/O. This is not a PB-scale catalog service.
- A changed parameter can affect upstream/downstream control through feedback. Mark such changes structural/nonlocal. The tool cannot infer undocumented dependencies.
- The demo exercises sequence job grouping but uses a stateless spatial filter; real temporal state/reset correctness needs adapter-specific testing.
- Full validation is empirical for a specific plan/run. A no-change observation yields recall=null. Periodic full runs remain necessary.
- A normalized bundle's execution_contract is an exporter obligation. Omitted changes cannot be discovered automatically.
- Output hashes establish byte differences, not quality regressions. Expected tuning differences and unacceptable regressions must be evaluated separately.
- Workstation paths/input digests are stored in plans and logs. Generated workspaces are excluded by .gitignore; inspect anything you choose to publish.
- Plan/run bindings detect mistakes, not adversarial tampering. Adapter executable version is not automatically hashed; record that version in execution_contract for reproducibility.
- No automatic trigger influence derivation, scenario inheritance resolver, cache reuse, GUI, resume, resource scheduler or distributed execution in v0.2.

Next useful contributions: a tested public RAW-format adapter; metric comparison policies; trace-derived influence with provenance; stronger schema validation; mutation experiments; indexed metadata; temporal state verification.
