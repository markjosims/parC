### Web app restructure
Currently using two tabs: Grammar config for editing config files, Test parser to apply FST I/O in realtime. Let's integrate the FST interaction logic into the Grammar config tab and remove the Test Parser tab.
This will require the following logic:
- Don't add a new input field for FST test functionns.
- Instead add a button that runs `FstRegistry.test_pattern_includes` on the current pattern using all strings in the `test_includes` attr and likewise with `test_excludes`.
- We need to track two states:
    - Whether the registry is up-to-date with YAML files (use `watchdog` with an event handler that calls `FstRegistry.initialize()` whenever files are changed.)
    - Whether the YAML files on disk are up-to-date with form data (use your best judgment how to do this: I'm guessing this will require JS?)