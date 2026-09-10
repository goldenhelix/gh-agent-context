# Server workspace templates (example tasks & workflows)

Tasks, workflows, plugins, and applications shipped as **workspace templates** on
this server. They are the best worked examples to copy from: each is a real,
runnable definition.

Source on this server:
- `/opt/server_templates/workspaces/core/Automation/`
- `/opt/server_templates/workspaces/example/Automation/`
- `/opt/server_templates/workspaces/test/Automation/`

Each template's `Automation/` tree has `Workflows/` (tasks and workflows),
`Applications/`, and `Plugins/` subfolders; that folder name is what the
server discovers each definition as.

`core` is copied into every new workspace's `Automation/` tree by default
when the workspace is created (`ghadmin workspace-create`, opt out with
`--no-core`), so its Applications and Plugins are already present there,
not something you need to copy in yourself. `example` and `test` are
opt-in template folders you copy from explicitly.

Application and plugin *definitions themselves* (like VSAgent's) live in
the versioned application/plugin registry, not in a workspace template;
they're installed into a workspace with the built-in `System/application_checkout`
and `System/plugin_checkout` tasks.

Since this tree changes with each release, don't rely on a stale mirror of
it here. Enumerate what's actually on the server:

```sh
ls -R /opt/server_templates/workspaces/*/Automation
gautil client task-list                 # includes the built-in System/ tasks
gautil client task-list --path=<prefix>
```

Read a definition in place (`Read /opt/server_templates/workspaces/<template>/Automation/...`)
to see its parameters and description before copying it into your own
workspace's `Automation/` tree and adapting it.
