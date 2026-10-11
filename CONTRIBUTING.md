# Contributing

Start with an issue describing the behavior and a small reproducible input. Keep the core vendor-neutral. Use generated or redistributable fixtures. Submit focused merge requests with tests demonstrating the behavior or failure mode.

```sh
python -m unittest discover -s tests -v
python -m isp_impact demo --out contribution-demo
```

Selection changes should demonstrate both positive inclusion and exclusion behavior, especially interpolation boundaries, missing metadata and complete sequence replay. Runner changes should preserve failure propagation and plan/input binding. Public API changes require matching format documentation.

Runtime dependencies are currently standard library only. Discuss new dependencies before adding them. Contributions are provided under the repository's MIT license.
