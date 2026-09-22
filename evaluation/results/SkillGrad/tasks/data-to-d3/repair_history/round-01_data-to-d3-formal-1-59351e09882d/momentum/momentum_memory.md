### materialize-required-deliverables-before-end | workflow | executor ends run without writing required output files
- anchor: (none yet)
- appeared_in: iter_0
- description: For generation/implementation tasks with a required output inventory (e.g., specific files under /root/output), the executor may terminate (end_turn) without creating any artifacts. This is an upstream workflow failure: the task cannot be evaluated and no downstream visualization logic matters. In this iteration the output inventory was empty, meaning index.html and supporting js/css/data assets were never written or copied.
- latest_executor_action: Before ending the run, always materialize the required deliverables at the specified paths. Create required directories, copy any required input datasets into the output data folder, write the HTML/CSS/JS assets, and then verify that every required file exists and is non-empty (and ideally can be opened) before issuing end_turn.
- remedy_log:
  - iter_0 | diagnosis: run produced no output artifacts; agent ended without writing /root/output/index.html and supporting folders/files
            | patch: (pending) add an explicit deliverables checklist + pre-end filesystem verification step to the base skill
