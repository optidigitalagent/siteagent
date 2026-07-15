# SiteAgent Web Studio IDE wrapper

The production runner resolves skills only from `.agents/skills`; this package is optional IDE
convenience distribution and cannot change `python -m site_agent.cli go` behavior.

Validate the checked-in wrapper from the repository root:

```powershell
python C:\Users\Admin\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\siteagent-web-studio
python -m unittest tests.test_creative_studio.PluginBundleTests
```

For the repository marketplace, install its root once in Codex, then add the plugin from the
`siteagent-web-studio` marketplace entry. After an update run the plugin cachebuster helper and
reinstall; begin a new Codex thread so it discovers the refreshed skills.
