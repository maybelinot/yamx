from jinja2.sandbox import SandboxedEnvironment

from yamx.constants import NON_EXISTING_STR


def get_jinja_env():
    # TODO: make a singleton class
    env = SandboxedEnvironment(
        # variable parsing is disabled this way
        variable_start_string=NON_EXISTING_STR,
        variable_end_string=NON_EXISTING_STR,
        # yaml parsing relies on this configuration
        trim_blocks=True,
        # strips leading spaces and tabs before jinja block
        lstrip_blocks=True,
        # keep new line at the end of the file
        keep_trailing_newline=True,
    )
    env.filters = {}
    env.globals = {}
    return env
